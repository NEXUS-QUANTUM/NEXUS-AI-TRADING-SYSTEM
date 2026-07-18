# trading/signals/realtime.py
"""
NEXUS AI TRADING SYSTEM - Real-time Signal Processing
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides real-time signal processing with support for:
- Real-time signal generation and validation
- Signal filtering and prioritization
- Multi-strategy signal management
- Signal confidence aggregation
- Conflict resolution
- Performance tracking
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable
from collections import defaultdict, deque

import numpy as np

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import MarketData, OrderBook, Trade
from .base import Signal, SignalType, SignalStrength
from .storage import SignalRecord, SignalStorage, SignalStatus, SignalOutcome
from ..strategies.base import BaseStrategy

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class SignalPriority(str, Enum):
    """Priority levels for signals"""
    CRITICAL = "critical"      # Must execute immediately
    HIGH = "high"              # Execute as soon as possible
    MEDIUM = "medium"          # Execute under normal conditions
    LOW = "low"                # Execute only if favorable
    BACKGROUND = "background"  # Low priority, execute when idle


class SignalConflictResolution(str, Enum):
    """Strategies for resolving conflicting signals"""
    HIGHEST_CONFIDENCE = "highest_confidence"      # Highest confidence wins
    HIGHEST_PRIORITY = "highest_priority"          # Highest priority wins
    MAJORITY = "majority"                          # Majority vote
    WEIGHTED = "weighted"                          # Weighted by strategy performance
    AGGRESSIVE = "aggressive"                      # Take most aggressive signal
    CONSERVATIVE = "conservative"                  # Take most conservative
    REJECT_ALL = "reject_all"                      # Reject all conflicting signals
    STRATEGY_PRIORITY = "strategy_priority"        # Based on strategy priority


@dataclass
class SignalEnvelope:
    """
    Wrapper for signals with additional context and metadata.
    """
    signal: Signal
    strategy_id: str
    strategy_name: str
    priority: SignalPriority = SignalPriority.MEDIUM
    weight: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    is_processed: bool = False
    is_executed: bool = False
    execution_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def age_seconds(self) -> float:
        """Get signal age in seconds."""
        return (datetime.utcnow() - self.timestamp).total_seconds()
    
    @property
    def is_expired(self) -> bool:
        """Check if signal has expired."""
        return self.expires_at and datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal": self.signal.to_dict(),
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "priority": self.priority.value,
            "weight": self.weight,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_processed": self.is_processed,
            "is_executed": self.is_executed,
            "metadata": self.metadata,
        }


@dataclass
class SignalAggregation:
    """
    Aggregated signal from multiple strategies.
    """
    symbol: str
    signal_type: SignalType
    strength: SignalStrength
    confidence: float
    priority: SignalPriority
    source_signals: List[SignalEnvelope]
    aggregate_score: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# REAL-TIME SIGNAL PROCESSOR
# ============================================================================

class RealtimeSignalProcessor:
    """
    Real-time signal processing and management system.
    
    Features:
    - Multi-strategy signal collection
    - Signal filtering and validation
    - Conflict resolution
    - Priority-based processing
    - Signal aggregation
    - Performance tracking
    """
    
    def __init__(
        self,
        signal_storage: Optional[SignalStorage] = None,
        conflict_resolution: SignalConflictResolution = SignalConflictResolution.HIGHEST_CONFIDENCE,
        max_signal_age: int = 60,  # seconds
        max_queue_size: int = 1000,
    ):
        """
        Initialize the real-time signal processor.
        
        Args:
            signal_storage: Signal storage instance
            conflict_resolution: Conflict resolution strategy
            max_signal_age: Maximum signal age in seconds
            max_queue_size: Maximum queue size
        """
        self.signal_storage = signal_storage or SignalStorage()
        self.conflict_resolution = conflict_resolution
        self.max_signal_age = max_signal_age
        self.max_queue_size = max_queue_size
        
        # Signal queues
        self._signal_queue: deque = deque(maxlen=max_queue_size)
        self._pending_signals: Dict[str, SignalEnvelope] = {}
        self._processed_signals: Dict[str, SignalEnvelope] = {}
        self._rejected_signals: Dict[str, SignalEnvelope] = {}
        
        # Strategy registry
        self._strategies: Dict[str, BaseStrategy] = {}
        self._strategy_weights: Dict[str, float] = {}
        self._strategy_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Signal history
        self._signal_history: List[SignalEnvelope] = []
        self._aggregated_signals: List[SignalAggregation] = []
        
        # Performance tracking
        self._performance = {
            "total_signals_received": 0,
            "total_signals_processed": 0,
            "total_signals_executed": 0,
            "total_signals_rejected": 0,
            "signals_by_type": defaultdict(int),
            "signals_by_strategy": defaultdict(int),
            "avg_processing_time_ms": 0.0,
            "conflicts_resolved": 0,
        }
        
        # Callbacks
        self._on_signal_callbacks: List[Callable[[SignalEnvelope], Awaitable[None]]] = []
        self._on_execution_callbacks: List[Callable[[SignalEnvelope, Dict[str, Any]], Awaitable[None]]] = []
        self._on_rejection_callbacks: List[Callable[[SignalEnvelope, str], Awaitable[None]]] = []
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Processing task
        self._processing_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        
        self.logger = logger
    
    # ========================================================================
    # CALLBACK MANAGEMENT
    # ========================================================================
    
    def on_signal(self, callback: Callable[[SignalEnvelope], Awaitable[None]]) -> None:
        """Register callback for signal receipt."""
        self._on_signal_callbacks.append(callback)
    
    def on_execution(self, callback: Callable[[SignalEnvelope, Dict[str, Any]], Awaitable[None]]) -> None:
        """Register callback for signal execution."""
        self._on_execution_callbacks.append(callback)
    
    def on_rejection(self, callback: Callable[[SignalEnvelope, str], Awaitable[None]]) -> None:
        """Register callback for signal rejection."""
        self._on_rejection_callbacks.append(callback)
    
    async def _trigger_signal_callbacks(self, envelope: SignalEnvelope) -> None:
        """Trigger signal callbacks."""
        for callback in self._on_signal_callbacks:
            try:
                await callback(envelope)
            except Exception as e:
                self.logger.error(f"Error in signal callback: {e}")
    
    async def _trigger_execution_callbacks(self, envelope: SignalEnvelope, result: Dict[str, Any]) -> None:
        """Trigger execution callbacks."""
        for callback in self._on_execution_callbacks:
            try:
                await callback(envelope, result)
            except Exception as e:
                self.logger.error(f"Error in execution callback: {e}")
    
    async def _trigger_rejection_callbacks(self, envelope: SignalEnvelope, reason: str) -> None:
        """Trigger rejection callbacks."""
        for callback in self._on_rejection_callbacks:
            try:
                await callback(envelope, reason)
            except Exception as e:
                self.logger.error(f"Error in rejection callback: {e}")
    
    # ========================================================================
    # STRATEGY MANAGEMENT
    # ========================================================================
    
    def register_strategy(
        self,
        strategy: BaseStrategy,
        weight: float = 1.0,
        priority: SignalPriority = SignalPriority.MEDIUM,
    ) -> None:
        """
        Register a strategy with the processor.
        
        Args:
            strategy: Strategy instance
            weight: Strategy weight for aggregation
            priority: Default priority for signals from this strategy
        """
        strategy_id = strategy.strategy_id
        self._strategies[strategy_id] = strategy
        self._strategy_weights[strategy_id] = weight
        
        # Store priority in strategy metadata
        if not hasattr(strategy, "_signal_priority"):
            strategy._signal_priority = priority
        
        self.logger.info(f"Registered strategy {strategy.config.name} ({strategy_id})")
    
    def unregister_strategy(self, strategy_id: str) -> bool:
        """
        Unregister a strategy.
        
        Args:
            strategy_id: Strategy ID
            
        Returns:
            bool: True if strategy was unregistered
        """
        if strategy_id in self._strategies:
            del self._strategies[strategy_id]
            if strategy_id in self._strategy_weights:
                del self._strategy_weights[strategy_id]
            self.logger.info(f"Unregistered strategy {strategy_id}")
            return True
        return False
    
    def update_strategy_weight(self, strategy_id: str, weight: float) -> bool:
        """
        Update a strategy's weight.
        
        Args:
            strategy_id: Strategy ID
            weight: New weight
            
        Returns:
            bool: True if updated successfully
        """
        if strategy_id in self._strategy_weights:
            self._strategy_weights[strategy_id] = weight
            return True
        return False
    
    # ========================================================================
    # SIGNAL PROCESSING
    # ========================================================================
    
    async def process_signal(
        self,
        signal: Signal,
        strategy_id: str,
        strategy_name: str = "",
        priority: Optional[SignalPriority] = None,
        weight: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[SignalEnvelope]:
        """
        Process an incoming signal.
        
        Args:
            signal: Trading signal
            strategy_id: Strategy ID
            strategy_name: Strategy name
            priority: Signal priority
            weight: Signal weight
            metadata: Additional metadata
            
        Returns:
            Optional[SignalEnvelope]: Processed signal envelope
        """
        # Get strategy priority if not specified
        if priority is None:
            strategy = self._strategies.get(strategy_id)
            if strategy and hasattr(strategy, "_signal_priority"):
                priority = strategy._signal_priority
            else:
                priority = SignalPriority.MEDIUM
        
        # Get strategy weight if not specified
        if weight is None:
            weight = self._strategy_weights.get(strategy_id, 1.0)
        
        # Create envelope
        envelope = SignalEnvelope(
            signal=signal,
            strategy_id=strategy_id,
            strategy_name=strategy_name or strategy_id,
            priority=priority,
            weight=weight,
            expires_at=datetime.utcnow() + timedelta(seconds=self.max_signal_age),
            metadata=metadata or {},
        )
        
        # Update performance
        self._performance["total_signals_received"] += 1
        self._performance["signals_by_type"][signal.signal_type.value] += 1
        self._performance["signals_by_strategy"][strategy_id] += 1
        
        # Queue the signal
        async with self._lock:
            self._signal_queue.append(envelope)
            self._pending_signals[envelope.signal.signal_id] = envelope
        
        # Trigger callbacks
        await self._trigger_signal_callbacks(envelope)
        
        self.logger.info(
            f"Signal received: {signal.signal_type.value} {signal.symbol} "
            f"from {strategy_id} (priority: {priority.value}, confidence: {signal.confidence:.2f})"
        )
        
        return envelope
    
    async def _process_queue(self) -> None:
        """Process the signal queue."""
        while self._is_running:
            try:
                # Get signals from queue
                signals_to_process = []
                async with self._lock:
                    while self._signal_queue and len(signals_to_process) < 50:
                        envelope = self._signal_queue.popleft()
                        
                        # Check if signal is expired
                        if envelope.is_expired:
                            await self._reject_signal(envelope, "Signal expired")
                            continue
                        
                        signals_to_process.append(envelope)
                
                if not signals_to_process:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process signals
                for envelope in signals_to_process:
                    await self._process_single_signal(envelope)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing queue: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_single_signal(self, envelope: SignalEnvelope) -> None:
        """
        Process a single signal.
        
        Args:
            envelope: Signal envelope
        """
        start_time = time.time()
        
        try:
            # Validate signal
            if not await self._validate_signal(envelope):
                await self._reject_signal(envelope, "Validation failed")
                return
            
            # Check for conflicts
            conflict = await self._check_conflicts(envelope)
            if conflict:
                resolved = await self._resolve_conflict(envelope, conflict)
                if not resolved:
                    await self._reject_signal(envelope, "Conflict rejected")
                    return
            
            # Execute signal
            result = await self._execute_signal(envelope)
            
            if result.get("success", False):
                # Signal executed successfully
                envelope.is_executed = True
                envelope.execution_result = result
                self._performance["total_signals_executed"] += 1
                
                # Store in processed
                self._processed_signals[envelope.signal.signal_id] = envelope
                
                # Trigger execution callbacks
                await self._trigger_execution_callbacks(envelope, result)
                
                self.logger.info(
                    f"Signal executed: {envelope.signal.signal_type.value} {envelope.signal.symbol} "
                    f"(order_id: {result.get('order_id', 'unknown')})"
                )
            else:
                # Signal rejected by execution
                await self._reject_signal(envelope, result.get("reason", "Execution failed"))
            
            # Update performance
            processing_time = (time.time() - start_time) * 1000
            self._performance["avg_processing_time_ms"] = (
                (self._performance["avg_processing_time_ms"] * self._performance["total_signals_processed"] +
                 processing_time) / (self._performance["total_signals_processed"] + 1)
            )
            
        except Exception as e:
            self.logger.error(f"Error processing signal {envelope.signal.signal_id}: {e}")
            await self._reject_signal(envelope, f"Processing error: {str(e)}")
    
    async def _validate_signal(self, envelope: SignalEnvelope) -> bool:
        """
        Validate a signal.
        
        Args:
            envelope: Signal envelope
            
        Returns:
            bool: True if signal is valid
        """
        signal = envelope.signal
        
        # Check basic signal properties
        if not signal.symbol:
            self.logger.warning(f"Signal {signal.signal_id} missing symbol")
            return False
        
        if signal.price <= 0:
            self.logger.warning(f"Signal {signal.signal_id} invalid price")
            return False
        
        if signal.confidence < 0 or signal.confidence > 1:
            self.logger.warning(f"Signal {signal.signal_id} invalid confidence")
            return False
        
        # Check if signal type is valid
        if signal.signal_type in [SignalType.NEUTRAL, SignalType.HOLD]:
            self.logger.debug(f"Signal {signal.signal_id} is neutral/hold, skipping")
            return False
        
        # Check if signal is expired
        if envelope.is_expired:
            self.logger.debug(f"Signal {signal.signal_id} is expired")
            return False
        
        return True
    
    async def _check_conflicts(self, envelope: SignalEnvelope) -> Optional[List[SignalEnvelope]]:
        """
        Check for conflicts with existing signals.
        
        Args:
            envelope: Signal envelope
            
        Returns:
            Optional[List[SignalEnvelope]]: Conflicting signals
        """
        symbol = envelope.signal.symbol
        
        # Find pending signals for the same symbol
        conflicts = []
        for pending in self._pending_signals.values():
            if pending.signal.symbol == symbol and not pending.is_processed:
                conflicts.append(pending)
        
        # Also check active (executed but not closed) signals
        for executed in self._processed_signals.values():
            if (executed.signal.symbol == symbol and 
                executed.is_executed and 
                not executed.is_processed):
                conflicts.append(executed)
        
        return conflicts if conflicts else None
    
    async def _resolve_conflict(
        self,
        envelope: SignalEnvelope,
        conflicts: List[SignalEnvelope],
    ) -> bool:
        """
        Resolve conflicts between signals.
        
        Args:
            envelope: New signal envelope
            conflicts: Conflicting signals
            
        Returns:
            bool: True if new signal should proceed
        """
        self._performance["conflicts_resolved"] += 1
        
        resolution = self.conflict_resolution
        
        if resolution == SignalConflictResolution.HIGHEST_CONFIDENCE:
            # Keep signal with highest confidence
            all_signals = conflicts + [envelope]
            best = max(all_signals, key=lambda x: x.signal.confidence)
            return best.signal.signal_id == envelope.signal.signal_id
        
        elif resolution == SignalConflictResolution.HIGHEST_PRIORITY:
            # Keep signal with highest priority
            priority_order = {
                SignalPriority.CRITICAL: 5,
                SignalPriority.HIGH: 4,
                SignalPriority.MEDIUM: 3,
                SignalPriority.LOW: 2,
                SignalPriority.BACKGROUND: 1,
            }
            all_signals = conflicts + [envelope]
            best = max(all_signals, key=lambda x: priority_order.get(x.priority, 0))
            return best.signal.signal_id == envelope.signal.signal_id
        
        elif resolution == SignalConflictResolution.MAJORITY:
            # Check if signal type has majority
            signal_types = [s.signal.signal_type for s in conflicts]
            if envelope.signal.signal_type.value in signal_types:
                # Count occurrences
                count = sum(1 for t in signal_types if t == envelope.signal.signal_type.value)
                return count > len(signal_types) / 2
            return False
        
        elif resolution == SignalConflictResolution.WEIGHTED:
            # Weighted by strategy performance
            all_signals = conflicts + [envelope]
            weighted = {}
            for s in all_signals:
                weight = self._strategy_weights.get(s.strategy_id, 1.0)
                performance = self._strategy_performance.get(s.strategy_id, {})
                perf_score = performance.get("win_rate", 0.5)
                weighted[s.signal.signal_id] = s.signal.confidence * weight * perf_score
            
            best_id = max(weighted, key=weighted.get)
            return best_id == envelope.signal.signal_id
        
        elif resolution == SignalConflictResolution.AGGRESSIVE:
            # Take buy over sell, strong over weak
            if envelope.signal.signal_type == SignalType.BUY:
                return True
            elif envelope.signal.signal_type == SignalType.SELL:
                # Check if any buy signals exist
                for s in conflicts:
                    if s.signal.signal_type == SignalType.BUY:
                        return False
                return True
            return False
        
        elif resolution == SignalConflictResolution.CONSERVATIVE:
            # Take sell over buy, weak over strong
            if envelope.signal.signal_type == SignalType.SELL:
                return True
            elif envelope.signal.signal_type == SignalType.BUY:
                for s in conflicts:
                    if s.signal.signal_type == SignalType.SELL:
                        return False
                return True
            return False
        
        elif resolution == SignalConflictResolution.REJECT_ALL:
            # Reject all conflicting signals
            for s in conflicts:
                await self._reject_signal(s, "Conflict rejected by ALL strategy")
            return True
        
        elif resolution == SignalConflictResolution.STRATEGY_PRIORITY:
            # Based on strategy priority
            strategy_priorities = {}
            for s in conflicts + [envelope]:
                strategy_priorities[s.strategy_id] = self._strategy_weights.get(s.strategy_id, 1.0)
            
            # Check if this strategy has highest priority
            current_priority = strategy_priorities.get(envelope.strategy_id, 0)
            max_priority = max(strategy_priorities.values())
            return current_priority == max_priority
        
        # Default: accept if no conflicts
        return True
    
    async def _execute_signal(self, envelope: SignalEnvelope) -> Dict[str, Any]:
        """
        Execute a signal (placeholder for actual execution).
        
        Args:
            envelope: Signal envelope
            
        Returns:
            Dict[str, Any]: Execution result
        """
        # In production, this would call the order execution system
        # For now, simulate success
        return {
            "success": True,
            "order_id": f"order_{int(time.time())}",
            "executed_price": envelope.signal.price,
            "executed_quantity": envelope.signal.position_size or 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _reject_signal(self, envelope: SignalEnvelope, reason: str) -> None:
        """
        Reject a signal.
        
        Args:
            envelope: Signal envelope
            reason: Rejection reason
        """
        envelope.is_processed = True
        self._rejected_signals[envelope.signal.signal_id] = envelope
        
        if envelope.signal.signal_id in self._pending_signals:
            del self._pending_signals[envelope.signal.signal_id]
        
        self._performance["total_signals_rejected"] += 1
        
        await self._trigger_rejection_callbacks(envelope, reason)
        
        self.logger.debug(
            f"Signal rejected: {envelope.signal.signal_type.value} {envelope.signal.symbol} "
            f"from {envelope.strategy_id}: {reason}"
        )
    
    # ========================================================================
    # SIGNAL AGGREGATION
    # ========================================================================
    
    async def aggregate_signals(self, symbol: Optional[str] = None) -> List[SignalAggregation]:
        """
        Aggregate signals by symbol and signal type.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List[SignalAggregation]: Aggregated signals
        """
        # Get pending signals
        pending = list(self._pending_signals.values())
        
        if symbol:
            pending = [s for s in pending if s.signal.symbol == symbol]
        
        if not pending:
            return []
        
        # Group by symbol and signal type
        grouped = defaultdict(list)
        for envelope in pending:
            key = (envelope.signal.symbol, envelope.signal.signal_type)
            grouped[key].append(envelope)
        
        aggregations = []
        
        for (symbol, signal_type), signals in grouped.items():
            # Calculate aggregate metrics
            confidences = [s.signal.confidence for s in signals]
            weights = [s.weight for s in signals]
            
            weighted_confidence = sum(c * w for c, w in zip(confidences, weights)) / sum(weights)
            
            # Determine aggregate strength
            strengths = [s.signal.strength for s in signals]
            strength_order = {
                SignalStrength.VERY_STRONG: 4,
                SignalStrength.STRONG: 3,
                SignalStrength.MEDIUM: 2,
                SignalStrength.WEAK: 1,
            }
            avg_strength = sum(strength_order.get(s, 0) for s in strengths) / len(signals)
            
            if avg_strength >= 3.5:
                aggregate_strength = SignalStrength.VERY_STRONG
            elif avg_strength >= 2.5:
                aggregate_strength = SignalStrength.STRONG
            elif avg_strength >= 1.5:
                aggregate_strength = SignalStrength.MEDIUM
            else:
                aggregate_strength = SignalStrength.WEAK
            
            # Determine priority
            priorities = [s.priority for s in signals]
            priority_order = {
                SignalPriority.CRITICAL: 5,
                SignalPriority.HIGH: 4,
                SignalPriority.MEDIUM: 3,
                SignalPriority.LOW: 2,
                SignalPriority.BACKGROUND: 1,
            }
            max_priority = max(priorities, key=lambda x: priority_order.get(x, 0))
            
            # Calculate aggregate score
            aggregate_score = weighted_confidence * (avg_strength / 4)
            
            aggregation = SignalAggregation(
                symbol=symbol,
                signal_type=signal_type,
                strength=aggregate_strength,
                confidence=weighted_confidence,
                priority=max_priority,
                source_signals=signals,
                aggregate_score=aggregate_score,
                metadata={
                    "signal_count": len(signals),
                    "avg_strength": avg_strength,
                    "weighted_confidence": weighted_confidence,
                },
            )
            
            aggregations.append(aggregation)
        
        # Sort by priority and confidence
        priority_order = {
            SignalPriority.CRITICAL: 5,
            SignalPriority.HIGH: 4,
            SignalPriority.MEDIUM: 3,
            SignalPriority.LOW: 2,
            SignalPriority.BACKGROUND: 1,
        }
        aggregations.sort(
            key=lambda x: (priority_order.get(x.priority, 0), x.confidence),
            reverse=True,
        )
        
        self._aggregated_signals = aggregations
        
        return aggregations
    
    async def get_best_signal(self, symbol: Optional[str] = None) -> Optional[SignalAggregation]:
        """
        Get the best aggregated signal for a symbol.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            Optional[SignalAggregation]: Best signal or None
        """
        aggregations = await self.aggregate_signals(symbol)
        return aggregations[0] if aggregations else None
    
    # ========================================================================
    # PERFORMANCE TRACKING
    # ========================================================================
    
    def update_strategy_performance(
        self,
        strategy_id: str,
        win_rate: float,
        total_pnl: float,
        trades: int,
    ) -> None:
        """
        Update strategy performance metrics.
        
        Args:
            strategy_id: Strategy ID
            win_rate: Win rate percentage
            total_pnl: Total P&L
            trades: Number of trades
        """
        self._strategy_performance[strategy_id] = {
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "trades": trades,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get processor performance metrics.
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        total_processed = self._performance["total_signals_processed"]
        
        return {
            **self._performance,
            "queue_size": len(self._signal_queue),
            "pending_signals": len(self._pending_signals),
            "processed_signals": len(self._processed_signals),
            "rejected_signals": len(self._rejected_signals),
            "active_strategies": len(self._strategies),
            "aggregated_signals": len(self._aggregated_signals),
            "strategy_performance": dict(self._strategy_performance),
            "avg_processing_time_ms": self._performance["avg_processing_time_ms"],
        }
    
    # ========================================================================
    # LIFECYCLE MANAGEMENT
    # ========================================================================
    
    async def start(self) -> None:
        """Start the signal processor."""
        if self._is_running:
            return
        
        self._is_running = True
        self._processing_task = asyncio.create_task(self._process_queue())
        self.logger.info("Real-time signal processor started")
    
    async def stop(self) -> None:
        """Stop the signal processor."""
        self._is_running = False
        
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None
        
        self.logger.info("Real-time signal processor stopped")
    
    async def clear(self) -> None:
        """Clear all pending signals."""
        async with self._lock:
            self._signal_queue.clear()
            self._pending_signals.clear()
            self.logger.info("Signal processor cleared")
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "SignalPriority",
    "SignalConflictResolution",
    
    # Models
    "SignalEnvelope",
    "SignalAggregation",
    
    # Processor
    "RealtimeSignalProcessor",
]
