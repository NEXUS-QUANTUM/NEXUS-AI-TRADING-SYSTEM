# trading/signals/aggregator.py
"""
NEXUS AI TRADING SYSTEM - Signal Aggregator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides signal aggregation capabilities including:
- Multi-strategy signal aggregation
- Consensus-based signal formation
- Weighted signal combination
- Conflict resolution
- Signal fusion
- Real-time aggregation
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
from .base import Signal, SignalType, SignalStrength, SignalSource
from .realtime import SignalEnvelope, SignalPriority
from .confidence import ConfidenceScoringEngine, ConfidenceResult

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class AggregationMethod(str, Enum):
    """Methods for signal aggregation"""
    WEIGHTED_AVERAGE = "weighted_average"
    MAJORITY_VOTE = "majority_vote"
    CONSENSUS = "consensus"
    MAXIMUM_CONFIDENCE = "maximum_confidence"
    MINIMUM_CONFIDENCE = "minimum_confidence"
    MEDIAN = "median"
    DEMOCRATIC = "democratic"
    STRATEGY_PRIORITY = "strategy_priority"
    ADAPTIVE = "adaptive"


class ConflictResolution(str, Enum):
    """Conflict resolution strategies"""
    HIGHEST_CONFIDENCE = "highest_confidence"
    HIGHEST_PRIORITY = "highest_priority"
    MAJORITY = "majority"
    WEIGHTED_VOTE = "weighted_vote"
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"
    NEUTRAL = "neutral"
    REJECT_ALL = "reject_all"


@dataclass
class AggregatorConfig:
    """Configuration for signal aggregator"""
    # Aggregation method
    method: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE
    conflict_resolution: ConflictResolution = ConflictResolution.HIGHEST_CONFIDENCE
    
    # Weight configuration
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    default_weight: float = 1.0
    
    # Thresholds
    min_agreement: float = 0.5  # Minimum agreement for consensus
    min_confidence: float = 0.3
    max_confidence: float = 0.95
    signal_threshold: float = 0.5
    
    # Time decay
    time_decay: bool = True
    decay_rate: float = 0.1  # Per hour
    
    # Aggregation limits
    max_signals_per_symbol: int = 10
    min_signals_for_aggregation: int = 1
    max_signals_for_aggregation: int = 5
    
    # Output
    include_source_signals: bool = True
    include_confidence_breakdown: bool = True


@dataclass
class AggregatedSignal:
    """Result of signal aggregation"""
    symbol: str
    signal_type: SignalType
    strength: SignalStrength
    confidence: float
    priority: SignalPriority
    source_signals: List[Signal]
    source_weights: List[float]
    consensus_score: float
    conflict_resolution_used: ConflictResolution
    method_used: AggregationMethod
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_signal(self) -> Signal:
        """Convert to standard Signal."""
        return Signal(
            symbol=self.symbol,
            signal_type=self.signal_type,
            strength=self.strength,
            confidence=self.confidence,
            timestamp=self.timestamp,
            source=SignalSource.STRATEGY,
            metadata={
                "aggregated": True,
                "source_count": len(self.source_signals),
                "consensus_score": self.consensus_score,
                "method": self.method_used.value,
                "source_signals": [s.signal_id for s in self.source_signals],
                "source_weights": self.source_weights,
            },
            tags=["aggregated"],
            priority=self._priority_to_int(),
        )
    
    def _priority_to_int(self) -> int:
        """Convert priority to integer."""
        mapping = {
            SignalPriority.CRITICAL: 10,
            SignalPriority.HIGH: 8,
            SignalPriority.MEDIUM: 5,
            SignalPriority.LOW: 3,
            SignalPriority.BACKGROUND: 1,
        }
        return mapping.get(self.priority, 5)


@dataclass
class AggregationStats:
    """Statistics for signal aggregation"""
    total_signals_aggregated: int = 0
    total_aggregations: int = 0
    signals_by_type: Dict[str, int] = field(default_factory=dict)
    signals_by_strategy: Dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    avg_consensus_score: float = 0.0
    conflict_resolutions: Dict[str, int] = field(default_factory=dict)
    last_aggregation: Optional[datetime] = None


# ============================================================================
# SIGNAL AGGREGATOR
# ============================================================================

class SignalAggregator:
    """
    Aggregates signals from multiple strategies.
    
    Features:
    - Multi-strategy signal aggregation
    - Consensus-based signal formation
    - Weighted signal combination
    - Conflict resolution
    - Real-time aggregation
    - Performance tracking
    """
    
    def __init__(
        self,
        config: Optional[AggregatorConfig] = None,
        confidence_engine: Optional[ConfidenceScoringEngine] = None,
    ):
        """
        Initialize the signal aggregator.
        
        Args:
            config: Aggregator configuration
            confidence_engine: Confidence scoring engine
        """
        self.config = config or AggregatorConfig()
        self.confidence_engine = confidence_engine or ConfidenceScoringEngine()
        
        # Signal storage
        self._pending_signals: Dict[str, List[Signal]] = defaultdict(list)
        self._aggregated_signals: List[AggregatedSignal] = []
        self._signal_history: deque = deque(maxlen=10000)
        
        # Statistics
        self._stats = AggregationStats()
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger = logger
    
    # ========================================================================
    # SIGNAL AGGREGATION
    # ========================================================================
    
    async def add_signal(
        self,
        signal: Signal,
        strategy_id: str,
        weight: Optional[float] = None,
    ) -> None:
        """
        Add a signal for aggregation.
        
        Args:
            signal: Signal to add
            strategy_id: Strategy ID
            weight: Strategy weight
        """
        async with self._lock:
            symbol = signal.symbol
            
            # Add signal to pending
            if symbol not in self._pending_signals:
                self._pending_signals[symbol] = []
            
            self._pending_signals[symbol].append(signal)
            
            # Update stats
            self._stats.signals_by_strategy[strategy_id] = (
                self._stats.signals_by_strategy.get(strategy_id, 0) + 1
            )
            
            # Trim if too many signals
            if len(self._pending_signals[symbol]) > self.config.max_signals_per_symbol:
                # Remove oldest signals
                self._pending_signals[symbol] = self._pending_signals[symbol][-self.config.max_signals_per_symbol:]
            
            self.logger.debug(
                f"Added signal for {symbol}: {signal.signal_type.value} "
                f"(confidence: {signal.confidence:.2f})"
            )
    
    async def aggregate(self, symbol: Optional[str] = None) -> List[AggregatedSignal]:
        """
        Aggregate pending signals.
        
        Args:
            symbol: Optional symbol to aggregate
            
        Returns:
            List[AggregatedSignal]: Aggregated signals
        """
        async with self._lock:
            symbols = [symbol] if symbol else list(self._pending_signals.keys())
            results = []
            
            for sym in symbols:
                if sym not in self._pending_signals or not self._pending_signals[sym]:
                    continue
                
                signals = self._pending_signals[sym]
                
                # Skip if not enough signals
                if len(signals) < self.config.min_signals_for_aggregation:
                    continue
                
                # Limit signals
                if len(signals) > self.config.max_signals_for_aggregation:
                    # Sort by confidence and take top N
                    signals = sorted(signals, key=lambda x: x.confidence, reverse=True)
                    signals = signals[:self.config.max_signals_for_aggregation]
                
                # Aggregate signals
                aggregated = await self._aggregate_signals(signals)
                
                if aggregated:
                    results.append(aggregated)
                    
                    # Clear aggregated signals
                    self._pending_signals[sym] = []
                    
                    # Store in history
                    self._aggregated_signals.append(aggregated)
                    self._signal_history.append(aggregated.to_signal())
                    
                    # Update stats
                    self._stats.total_aggregations += 1
                    self._stats.total_signals_aggregated += len(signals)
                    self._stats.last_aggregation = datetime.utcnow()
                    
                    self.logger.info(
                        f"Aggregated {len(signals)} signals for {sym}: "
                        f"{aggregated.signal_type.value} (confidence: {aggregated.confidence:.2f})"
                    )
            
            return results
    
    async def _aggregate_signals(self, signals: List[Signal]) -> Optional[AggregatedSignal]:
        """
        Aggregate a list of signals.
        
        Args:
            signals: Signals to aggregate
            
        Returns:
            Optional[AggregatedSignal]: Aggregated signal or None
        """
        if not signals:
            return None
        
        symbol = signals[0].symbol
        
        # Apply time decay
        if self.config.time_decay:
            signals = await self._apply_time_decay(signals)
        
        # Resolve conflicts
        resolved = await self._resolve_conflicts(signals)
        
        if not resolved:
            return None
        
        # Calculate aggregated values
        result = await self._calculate_aggregation(resolved)
        
        return result
    
    # ========================================================================
    # CONFLICT RESOLUTION
    # ========================================================================
    
    async def _resolve_conflicts(self, signals: List[Signal]) -> List[Signal]:
        """
        Resolve conflicts between signals.
        
        Args:
            signals: Signals to resolve
            
        Returns:
            List[Signal]: Resolved signals
        """
        # Group by signal type
        signal_groups = defaultdict(list)
        for signal in signals:
            signal_groups[signal.signal_type].append(signal)
        
        # If only one type, no conflict
        if len(signal_groups) <= 1:
            return signals
        
        # Resolve conflict
        resolution = self.config.conflict_resolution
        
        if resolution == ConflictResolution.HIGHEST_CONFIDENCE:
            return self._resolve_by_confidence(signal_groups)
        
        elif resolution == ConflictResolution.HIGHEST_PRIORITY:
            return self._resolve_by_priority(signal_groups)
        
        elif resolution == ConflictResolution.MAJORITY:
            return self._resolve_by_majority(signal_groups)
        
        elif resolution == ConflictResolution.WEIGHTED_VOTE:
            return self._resolve_by_weighted_vote(signal_groups)
        
        elif resolution == ConflictResolution.AGGRESSIVE:
            return self._resolve_aggressive(signal_groups)
        
        elif resolution == ConflictResolution.CONSERVATIVE:
            return self._resolve_conservative(signal_groups)
        
        elif resolution == ConflictResolution.REJECT_ALL:
            self._stats.conflict_resolutions["rejected_all"] = (
                self._stats.conflict_resolutions.get("rejected_all", 0) + 1
            )
            return []
        
        return signals
    
    def _resolve_by_confidence(
        self,
        signal_groups: Dict[SignalType, List[Signal]],
    ) -> List[Signal]:
        """Resolve by highest confidence."""
        best_group = max(
            signal_groups.items(),
            key=lambda x: max(s.confidence for s in x[1])
        )
        self._stats.conflict_resolutions["highest_confidence"] = (
            self._stats.conflict_resolutions.get("highest_confidence", 0) + 1
        )
        return best_group[1]
    
    def _resolve_by_priority(
        self,
        signal_groups: Dict[SignalType, List[Signal]],
    ) -> List[Signal]:
        """Resolve by highest priority."""
        priority_order = {
            SignalPriority.CRITICAL: 10,
            SignalPriority.HIGH: 8,
            SignalPriority.MEDIUM: 5,
            SignalPriority.LOW: 3,
            SignalPriority.BACKGROUND: 1,
        }
        
        def get_priority(signal: Signal) -> int:
            return signal.metadata.get("priority", 5)
        
        best_group = max(
            signal_groups.items(),
            key=lambda x: max(get_priority(s) for s in x[1])
        )
        self._stats.conflict_resolutions["highest_priority"] = (
            self._stats.conflict_resolutions.get("highest_priority", 0) + 1
        )
        return best_group[1]
    
    def _resolve_by_majority(
        self,
        signal_groups: Dict[SignalType, List[Signal]],
    ) -> List[Signal]:
        """Resolve by majority vote."""
        majority = max(signal_groups.items(), key=lambda x: len(x[1]))
        
        # Check if majority is clear
        total = sum(len(v) for v in signal_groups.values())
        if len(majority[1]) / total >= self.config.min_agreement:
            self._stats.conflict_resolutions["majority"] = (
                self._stats.conflict_resolutions.get("majority", 0) + 1
            )
            return majority[1]
        
        # No clear majority
        self._stats.conflict_resolutions["no_majority"] = (
            self._stats.conflict_resolutions.get("no_majority", 0) + 1
        )
        return []
    
    def _resolve_by_weighted_vote(
        self,
        signal_groups: Dict[SignalType, List[Signal]],
    ) -> List[Signal]:
        """Resolve by weighted vote."""
        weighted_scores = {}
        
        for signal_type, signals in signal_groups.items():
            score = sum(
                s.confidence * self.config.strategy_weights.get(
                    s.metadata.get("strategy_id", "default"),
                    self.config.default_weight,
                )
                for s in signals
            )
            weighted_scores[signal_type] = score
        
        best_type = max(weighted_scores, key=weighted_scores.get)
        total_score = sum(weighted_scores.values())
        
        if total_score > 0:
            agreement = weighted_scores[best_type] / total_score
            if agreement >= self.config.min_agreement:
                self._stats.conflict_resolutions["weighted_vote"] = (
                    self._stats.conflict_resolutions.get("weighted_vote", 0) + 1
                )
                return signal_groups[best_type]
        
        self._stats.conflict_resolutions["weighted_vote_failed"] = (
            self._stats.conflict_resolutions.get("weighted_vote_failed", 0) + 1
        )
        return []
    
    def _resolve_aggressive(
        self,
        signal_groups: Dict[SignalType, List[Signal]],
    ) -> List[Signal]:
        """Resolve aggressively (favor BUY)."""
        if SignalType.BUY in signal_groups:
            self._stats.conflict_resolutions["aggressive_buy"] = (
                self._stats.conflict_resolutions.get("aggressive_buy", 0) + 1
            )
            return signal_groups[SignalType.BUY]
        elif SignalType.SELL in signal_groups:
            return signal_groups[SignalType.SELL]
        return []
    
    def _resolve_conservative(
        self,
        signal_groups: Dict[SignalType, List[Signal]],
    ) -> List[Signal]:
        """Resolve conservatively (favor SELL)."""
        if SignalType.SELL in signal_groups:
            self._stats.conflict_resolutions["conservative_sell"] = (
                self._stats.conflict_resolutions.get("conservative_sell", 0) + 1
            )
            return signal_groups[SignalType.SELL]
        elif SignalType.BUY in signal_groups:
            return signal_groups[SignalType.BUY]
        return []
    
    # ========================================================================
    # AGGREGATION CALCULATION
    # ========================================================================
    
    async def _calculate_aggregation(
        self,
        signals: List[Signal],
    ) -> Optional[AggregatedSignal]:
        """
        Calculate aggregated signal.
        
        Args:
            signals: Signals to aggregate
            
        Returns:
            Optional[AggregatedSignal]: Aggregated signal
        """
        if not signals:
            return None
        
        symbol = signals[0].symbol
        
        # Get weights
        weights = []
        for signal in signals:
            strategy_id = signal.metadata.get("strategy_id", "default")
            weight = self.config.strategy_weights.get(strategy_id, self.config.default_weight)
            weights.append(weight)
        
        # Apply confidence adjustment
        confidences = [s.confidence for s in signals]
        adjusted_confidences = []
        
        for signal, weight in zip(signals, weights):
            # Adjust confidence with confidence engine
            result = await self.confidence_engine.calculate_confidence(signal)
            adjusted_confidences.append(result.confidence)
        
        # Calculate aggregation
        method = self.config.method
        
        if method == AggregationMethod.WEIGHTED_AVERAGE:
            aggregated_conf = self._weighted_average(adjusted_confidences, weights)
        
        elif method == AggregationMethod.MAJORITY_VOTE:
            aggregated_conf = self._majority_vote(signals)
        
        elif method == AggregationMethod.CONSENSUS:
            aggregated_conf = self._consensus(signals, adjusted_confidences, weights)
        
        elif method == AggregationMethod.MAXIMUM_CONFIDENCE:
            aggregated_conf = max(adjusted_confidences)
        
        elif method == AggregationMethod.MINIMUM_CONFIDENCE:
            aggregated_conf = min(adjusted_confidences)
        
        elif method == AggregationMethod.MEDIAN:
            aggregated_conf = np.median(adjusted_confidences)
        
        elif method == AggregationMethod.DEMOCRATIC:
            aggregated_conf = self._democratic(adjusted_confidences, weights)
        
        elif method == AggregationMethod.ADAPTIVE:
            aggregated_conf = self._adaptive(adjusted_confidences, weights, signals)
        
        else:
            aggregated_conf = self._weighted_average(adjusted_confidences, weights)
        
        # Apply thresholds
        aggregated_conf = max(self.config.min_confidence, aggregated_conf)
        aggregated_conf = min(self.config.max_confidence, aggregated_conf)
        
        # Determine signal type (majority vote)
        signal_types = [s.signal_type for s in signals]
        type_counts = defaultdict(int)
        for st in signal_types:
            type_counts[st] += 1
        
        majority_type = max(type_counts, key=type_counts.get)
        
        # Calculate consensus score
        consensus_score = self._calculate_consensus_score(signals, adjusted_confidences)
        
        # Determine strength
        if aggregated_conf >= 0.8:
            strength = SignalStrength.VERY_STRONG
        elif aggregated_conf >= 0.65:
            strength = SignalStrength.STRONG
        elif aggregated_conf >= 0.5:
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.WEAK
        
        # Determine priority
        priority = self._determine_priority(signals, aggregated_conf)
        
        return AggregatedSignal(
            symbol=symbol,
            signal_type=majority_type,
            strength=strength,
            confidence=aggregated_conf,
            priority=priority,
            source_signals=signals,
            source_weights=weights,
            consensus_score=consensus_score,
            conflict_resolution_used=self.config.conflict_resolution,
            method_used=self.config.method,
            metadata={
                "strategy_ids": [s.metadata.get("strategy_id", "default") for s in signals],
                "strategy_names": [s.metadata.get("strategy_name", "") for s in signals],
                "original_confidences": confidences,
                "adjusted_confidences": adjusted_confidences,
                "weights": weights,
                "signal_types": [s.signal_type.value for s in signals],
                "consensus_score": consensus_score,
                "source_count": len(signals),
            },
        )
    
    def _weighted_average(self, confidences: List[float], weights: List[float]) -> float:
        """Calculate weighted average."""
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.5
        return sum(c * w for c, w in zip(confidences, weights)) / total_weight
    
    def _majority_vote(self, signals: List[Signal]) -> float:
        """Calculate via majority vote."""
        confidences = [s.confidence for s in signals]
        return np.median(confidences)
    
    def _consensus(
        self,
        signals: List[Signal],
        confidences: List[float],
        weights: List[float],
    ) -> float:
        """Calculate consensus confidence."""
        # Check if all signals agree on direction
        types = [s.signal_type for s in signals]
        if len(set(types)) > 1:
            # Not all agree, reduce confidence
            return self._weighted_average(confidences, weights) * 0.7
        
        return self._weighted_average(confidences, weights)
    
    def _democratic(self, confidences: List[float], weights: List[float]) -> float:
        """Democratic aggregation."""
        # Each signal gets a vote regardless of weight
        return sum(confidences) / len(confidences) if confidences else 0.5
    
    def _adaptive(self, confidences: List[float], weights: List[float], signals: List[Signal]) -> float:
        """Adaptive aggregation."""
        # Combine weighted average and median based on consistency
        weighted_avg = self._weighted_average(confidences, weights)
        median = np.median(confidences)
        
        # Calculate consistency
        std = np.std(confidences) if len(confidences) > 1 else 0
        
        if std < 0.1:
            # High consistency, use weighted average
            return weighted_avg
        else:
            # Low consistency, use median
            return median
    
    def _calculate_consensus_score(
        self,
        signals: List[Signal],
        confidences: List[float],
    ) -> float:
        """Calculate consensus score."""
        if len(signals) <= 1:
            return 1.0
        
        # Check type agreement
        types = [s.signal_type for s in signals]
        type_agreement = len(set(types)) == 1
        
        # Calculate confidence spread
        confidence_std = np.std(confidences) if len(confidences) > 1 else 0
        confidence_agreement = 1 - min(1, confidence_std / 0.3)
        
        # Combine scores
        if type_agreement:
            return 0.5 + 0.5 * confidence_agreement
        else:
            return 0.5 * confidence_agreement
    
    def _determine_priority(
        self,
        signals: List[Signal],
        confidence: float,
    ) -> SignalPriority:
        """Determine priority based on signals and confidence."""
        # Check for critical signals
        for signal in signals:
            if signal.metadata.get("priority", 0) >= 8:
                return SignalPriority.CRITICAL
        
        # Based on confidence
        if confidence >= 0.8:
            return SignalPriority.HIGH
        elif confidence >= 0.6:
            return SignalPriority.MEDIUM
        elif confidence >= 0.4:
            return SignalPriority.LOW
        else:
            return SignalPriority.BACKGROUND
    
    # ========================================================================
    # TIME DECAY
    # ========================================================================
    
    async def _apply_time_decay(self, signals: List[Signal]) -> List[Signal]:
        """
        Apply time decay to signals.
        
        Args:
            signals: Signals to decay
            
        Returns:
            List[Signal]: Decayed signals
        """
        if not self.config.time_decay:
            return signals
        
        now = datetime.utcnow()
        decayed = []
        
        for signal in signals:
            age_hours = (now - signal.timestamp).total_seconds() / 3600
            decay_factor = math.exp(-self.config.decay_rate * age_hours)
            signal.confidence *= decay_factor
            signal.metadata["time_decay_factor"] = decay_factor
            decayed.append(signal)
        
        return decayed
    
    # ========================================================================
    # QUERY METHODS
    # ========================================================================
    
    def get_aggregated_signals(
        self,
        symbol: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 50,
    ) -> List[AggregatedSignal]:
        """
        Get aggregated signals.
        
        Args:
            symbol: Optional symbol filter
            min_confidence: Minimum confidence filter
            limit: Maximum number of signals
            
        Returns:
            List[AggregatedSignal]: Aggregated signals
        """
        signals = self._aggregated_signals
        
        if symbol:
            signals = [s for s in signals if s.symbol == symbol]
        
        if min_confidence is not None:
            signals = [s for s in signals if s.confidence >= min_confidence]
        
        # Sort by timestamp (newest first)
        signals = sorted(signals, key=lambda x: x.timestamp, reverse=True)
        
        return signals[:limit]
    
    def get_pending_signals(self, symbol: Optional[str] = None) -> Dict[str, List[Signal]]:
        """
        Get pending signals.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            Dict[str, List[Signal]]: Pending signals by symbol
        """
        if symbol:
            return {symbol: self._pending_signals.get(symbol, [])}
        return dict(self._pending_signals)
    
    def get_stats(self) -> AggregationStats:
        """
        Get aggregation statistics.
        
        Returns:
            AggregationStats: Aggregation statistics
        """
        return self._stats
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    def clear_pending(self, symbol: Optional[str] = None) -> None:
        """
        Clear pending signals.
        
        Args:
            symbol: Optional symbol to clear
        """
        if symbol:
            self._pending_signals[symbol] = []
        else:
            self._pending_signals.clear()
        self.logger.info("Cleared pending signals")
    
    def clear_history(self) -> None:
        """Clear signal history."""
        self._aggregated_signals.clear()
        self._signal_history.clear()
        self.logger.info("Cleared signal history")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "AggregationMethod",
    "ConflictResolution",
    
    # Models
    "AggregatorConfig",
    "AggregatedSignal",
    "AggregationStats",
    
    # Aggregator
    "SignalAggregator",
]
