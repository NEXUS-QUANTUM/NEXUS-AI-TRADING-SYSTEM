# trading/bots/arbitrage_bot/models/signal.py
# NEXUS AI TRADING SYSTEM - SIGNAL MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for trading signals, signal generation,
# signal processing, and signal validation for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Signal Models

This module provides comprehensive data models for:
- Signal generation and detection
- Signal validation and filtering
- Signal strength and confidence
- Signal timing and execution
- Signal aggregation and combination
- Signal history and performance
- Signal source tracking
- Signal quality metrics
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class SignalType(str, Enum):
    """Types of trading signals."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"
    SHORT = "short"
    COVER = "cover"
    REVERSE = "reverse"
    SCALE_IN = "scale_in"
    SCALE_OUT = "scale_out"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    REBALANCE = "rebalance"
    HEDGE = "hedge"
    NEUTRAL = "neutral"


class SignalStrength(str, Enum):
    """Signal strength levels."""
    VERY_WEAK = "very_weak"              # < 20% confidence
    WEAK = "weak"                        # 20-40% confidence
    MEDIUM = "medium"                    # 40-60% confidence
    STRONG = "strong"                    # 60-80% confidence
    VERY_STRONG = "very_strong"          # > 80% confidence


class SignalSource(str, Enum):
    """Sources of trading signals."""
    TECHNICAL = "technical"              # Technical analysis
    FUNDAMENTAL = "fundamental"          # Fundamental analysis
    ONCHAIN = "onchain"                  # On-chain data
    SENTIMENT = "sentiment"              # Sentiment analysis
    NEWS = "news"                        # News events
    SOCIAL = "social"                    # Social media
    ARBITRAGE = "arbitrage"              # Arbitrage detection
    ML = "ml"                            # Machine learning
    AI = "ai"                            # AI model
    PATTERN = "pattern"                  # Pattern recognition
    INDICATOR = "indicator"              # Technical indicators
    CUSTOM = "custom"                    # Custom source


class SignalStatus(str, Enum):
    """Status of a signal lifecycle."""
    GENERATED = "generated"              # Signal generated
    VALIDATED = "validated"              # Signal validated
    PENDING = "pending"                  # Pending execution
    EXECUTED = "executed"                # Signal executed
    PARTIALLY_EXECUTED = "partially_executed"  # Partially executed
    FAILED = "failed"                    # Execution failed
    CANCELLED = "cancelled"              # Cancelled
    EXPIRED = "expired"                  # Expired
    SUPERSEDED = "superseded"            # Superseded by another signal
    IGNORED = "ignored"                  # Ignored


class SignalPriority(str, Enum):
    """Priority levels for signal execution."""
    CRITICAL = "critical"                # Immediate execution
    HIGH = "high"                        # Execute as soon as possible
    MEDIUM = "medium"                    # Normal priority
    LOW = "low"                          # Low priority
    BACKGROUND = "background"            # Background execution


class SignalValidationMethod(str, Enum):
    """Methods for signal validation."""
    CONFIRMATION = "confirmation"        # Requires confirmation
    MULTI_SOURCE = "multi_source"        # Multiple sources required
    THRESHOLD = "threshold"              # Strength threshold check
    TIMING = "timing"                    # Timing validation
    FILTER = "filter"                    # Filter-based validation
    CUSTOM = "custom"                    # Custom validation


# ====================================================================================
# SIGNAL MODELS
# ====================================================================================

@dataclass
class Signal:
    """
    Comprehensive trading signal model.
    """
    # Core fields
    signal_id: str = field(default_factory=lambda: str(uuid4()))
    type: SignalType = SignalType.BUY
    source: SignalSource = SignalSource.TECHNICAL
    symbol: str = ""
    exchange: str = ""
    
    # Signal details
    strength: SignalStrength = SignalStrength.MEDIUM
    confidence: float = 0.5              # 0-1
    price: float = 0.0
    quantity: float = 0.0
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0
    
    # Timing
    generated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=15))
    executed_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    
    # Status
    status: SignalStatus = SignalStatus.GENERATED
    priority: SignalPriority = SignalPriority.MEDIUM
    
    # Validation
    validation_method: SignalValidationMethod = SignalValidationMethod.CONFIRMATION
    validation_data: Dict[str, Any] = field(default_factory=dict)
    is_validated: bool = False
    validation_score: float = 0.0
    
    # Supporting data
    supporting_signals: List[str] = field(default_factory=list)  # signal_ids
    conflicting_signals: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Performance
    performance_score: float = 0.0       # -1 to 1
    historical_accuracy: float = 0.0     # 0-1
    
    # Execution
    execution_order_id: str = ""
    execution_quantity: float = 0.0
    execution_price: float = 0.0
    execution_errors: List[str] = field(default_factory=list)
    
    # Tags
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize derived fields."""
        self.confidence = min(max(self.confidence, 0.0), 1.0)
        
        # Set strength based on confidence
        if self.confidence < 0.2:
            self.strength = SignalStrength.VERY_WEAK
        elif self.confidence < 0.4:
            self.strength = SignalStrength.WEAK
        elif self.confidence < 0.6:
            self.strength = SignalStrength.MEDIUM
        elif self.confidence < 0.8:
            self.strength = SignalStrength.STRONG
        else:
            self.strength = SignalStrength.VERY_STRONG
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal_id": self.signal_id,
            "type": self.type.value if self.type else None,
            "source": self.source.value if self.source else None,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "strength": self.strength.value if self.strength else None,
            "confidence": self.confidence,
            "price": self.price,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "generated_at": self.generated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "status": self.status.value if self.status else None,
            "priority": self.priority.value if self.priority else None,
            "validation_method": self.validation_method.value if self.validation_method else None,
            "validation_data": self.validation_data,
            "is_validated": self.is_validated,
            "validation_score": self.validation_score,
            "supporting_signals": self.supporting_signals,
            "conflicting_signals": self.conflicting_signals,
            "metadata": self.metadata,
            "performance_score": self.performance_score,
            "historical_accuracy": self.historical_accuracy,
            "execution_order_id": self.execution_order_id,
            "execution_quantity": self.execution_quantity,
            "execution_price": self.execution_price,
            "execution_errors": self.execution_errors,
            "tags": self.tags
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        """Create from dictionary."""
        signal = cls(
            signal_id=data.get("signal_id", str(uuid4())),
            type=SignalType(data["type"]) if data.get("type") else SignalType.BUY,
            source=SignalSource(data["source"]) if data.get("source") else SignalSource.TECHNICAL,
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            strength=SignalStrength(data["strength"]) if data.get("strength") else SignalStrength.MEDIUM,
            confidence=data.get("confidence", 0.5),
            price=data.get("price", 0.0),
            quantity=data.get("quantity", 0.0),
            entry_price=data.get("entry_price", 0.0),
            target_price=data.get("target_price", 0.0),
            stop_loss=data.get("stop_loss", 0.0),
            status=SignalStatus(data["status"]) if data.get("status") else SignalStatus.GENERATED,
            priority=SignalPriority(data["priority"]) if data.get("priority") else SignalPriority.MEDIUM,
            validation_method=SignalValidationMethod(data["validation_method"]) if data.get("validation_method") else SignalValidationMethod.CONFIRMATION,
            validation_data=data.get("validation_data", {}),
            is_validated=data.get("is_validated", False),
            validation_score=data.get("validation_score", 0.0),
            supporting_signals=data.get("supporting_signals", []),
            conflicting_signals=data.get("conflicting_signals", []),
            metadata=data.get("metadata", {}),
            performance_score=data.get("performance_score", 0.0),
            historical_accuracy=data.get("historical_accuracy", 0.0),
            execution_order_id=data.get("execution_order_id", ""),
            execution_quantity=data.get("execution_quantity", 0.0),
            execution_price=data.get("execution_price", 0.0),
            execution_errors=data.get("execution_errors", []),
            tags=data.get("tags", [])
        )
        
        # Parse timestamps
        if data.get("generated_at"):
            signal.generated_at = datetime.fromisoformat(data["generated_at"])
        if data.get("expires_at"):
            signal.expires_at = datetime.fromisoformat(data["expires_at"])
        if data.get("executed_at"):
            signal.executed_at = datetime.fromisoformat(data["executed_at"])
        if data.get("validated_at"):
            signal.validated_at = datetime.fromisoformat(data["validated_at"])
            
        signal.__post_init__()
        return signal
        
    def is_expired(self) -> bool:
        """Check if signal has expired."""
        return datetime.utcnow() >= self.expires_at
        
    def is_actionable(self) -> bool:
        """Check if signal is actionable."""
        return self.status in [SignalStatus.GENERATED, SignalStatus.VALIDATED, SignalStatus.PENDING] and not self.is_expired()
        
    def is_valid(self) -> bool:
        """Check if signal is valid."""
        return self.is_validated and self.confidence > 0.3
        
    def validate(self, validation_score: float, validation_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Validate the signal.
        
        Args:
            validation_score: Validation score (0-1)
            validation_data: Additional validation data
        """
        self.is_validated = True
        self.validation_score = validation_score
        self.validated_at = datetime.utcnow()
        if validation_data:
            self.validation_data.update(validation_data)
            
        if self.validation_score >= 0.7:
            self.status = SignalStatus.VALIDATED
        else:
            self.status = SignalStatus.PENDING
            
    def execute(self, execution_price: float, execution_quantity: float, order_id: str = "") -> None:
        """
        Mark signal as executed.
        
        Args:
            execution_price: Execution price
            execution_quantity: Execution quantity
            order_id: Order ID
        """
        self.status = SignalStatus.EXECUTED
        self.executed_at = datetime.utcnow()
        self.execution_price = execution_price
        self.execution_quantity = execution_quantity
        if order_id:
            self.execution_order_id = order_id
            
    def fail(self, error: str) -> None:
        """
        Mark signal as failed.
        
        Args:
            error: Error message
        """
        self.status = SignalStatus.FAILED
        self.execution_errors.append(error)
        
    def cancel(self, reason: str = "") -> None:
        """
        Cancel the signal.
        
        Args:
            reason: Cancellation reason
        """
        self.status = SignalStatus.CANCELLED
        if reason:
            self.metadata["cancellation_reason"] = reason
            
    def get_signal_strength_score(self) -> float:
        """
        Get signal strength score.
        
        Returns:
            Strength score (0-1)
        """
        strength_map = {
            SignalStrength.VERY_WEAK: 0.1,
            SignalStrength.WEAK: 0.3,
            SignalStrength.MEDIUM: 0.5,
            SignalStrength.STRONG: 0.7,
            SignalStrength.VERY_STRONG: 0.9
        }
        return strength_map.get(self.strength, 0.5)


# ====================================================================================
# SIGNAL AGGREGATION MODELS
# ====================================================================================

@dataclass
class SignalAggregation:
    """
    Aggregation of multiple signals.
    """
    # Core fields
    aggregation_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    symbol: str = ""
    exchange: str = ""
    
    # Signals
    signals: List[Signal] = field(default_factory=list)
    aggregated_signal: Optional[Signal] = None
    
    # Consensus
    consensus_type: str = "majority"     # majority, consensus, weighted
    consensus_score: float = 0.0
    consensus_strength: SignalStrength = SignalStrength.MEDIUM
    
    # Voting
    total_signals: int = 0
    buy_signals: int = 0
    sell_signals: int = 0
    hold_signals: int = 0
    neutral_signals: int = 0
    
    # Weighted average
    weighted_confidence: float = 0.0
    weighted_signal: SignalType = SignalType.NEUTRAL
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate aggregation metrics."""
        self._calculate_aggregation()
        
    def _calculate_aggregation(self) -> None:
        """Calculate aggregation metrics."""
        if not self.signals:
            return
            
        self.total_signals = len(self.signals)
        
        # Count signal types
        for signal in self.signals:
            if signal.type == SignalType.BUY:
                self.buy_signals += 1
            elif signal.type == SignalType.SELL:
                self.sell_signals += 1
            elif signal.type == SignalType.HOLD:
                self.hold_signals += 1
            else:
                self.neutral_signals += 1
                
        # Determine consensus
        if self.buy_signals > self.sell_signals and self.buy_signals > self.hold_signals:
            self.aggregated_signal = Signal(
                type=SignalType.BUY,
                symbol=self.symbol,
                exchange=self.exchange,
                confidence=self._calculate_weighted_confidence(SignalType.BUY),
                source=SignalSource.CUSTOM
            )
        elif self.sell_signals > self.buy_signals and self.sell_signals > self.hold_signals:
            self.aggregated_signal = Signal(
                type=SignalType.SELL,
                symbol=self.symbol,
                exchange=self.exchange,
                confidence=self._calculate_weighted_confidence(SignalType.SELL),
                source=SignalSource.CUSTOM
            )
        else:
            self.aggregated_signal = Signal(
                type=SignalType.HOLD,
                symbol=self.symbol,
                exchange=self.exchange,
                confidence=0.5,
                source=SignalSource.CUSTOM
            )
            
        # Set consensus score
        self.consensus_score = self.aggregated_signal.confidence
        self.consensus_strength = self.aggregated_signal.strength
        
    def _calculate_weighted_confidence(self, signal_type: SignalType) -> float:
        """
        Calculate weighted confidence for a signal type.
        
        Args:
            signal_type: Signal type
            
        Returns:
            Weighted confidence
        """
        signals_of_type = [s for s in self.signals if s.type == signal_type]
        if not signals_of_type:
            return 0.0
            
        total_weight = sum(s.confidence for s in signals_of_type)
        weighted_sum = sum(s.confidence * s.confidence for s in signals_of_type)
        
        if total_weight > 0:
            return weighted_sum / total_weight
        return 0.0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "aggregation_id": self.aggregation_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "exchange": self.exchange,
            "signals": [s.to_dict() for s in self.signals],
            "aggregated_signal": self.aggregated_signal.to_dict() if self.aggregated_signal else None,
            "consensus_type": self.consensus_type,
            "consensus_score": self.consensus_score,
            "consensus_strength": self.consensus_strength.value if self.consensus_strength else None,
            "total_signals": self.total_signals,
            "buy_signals": self.buy_signals,
            "sell_signals": self.sell_signals,
            "hold_signals": self.hold_signals,
            "neutral_signals": self.neutral_signals,
            "weighted_confidence": self.weighted_confidence,
            "weighted_signal": self.weighted_signal.value if self.weighted_signal else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalAggregation":
        """Create from dictionary."""
        agg = cls(
            aggregation_id=data.get("aggregation_id", str(uuid4())),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            signals=[Signal.from_dict(s) for s in data.get("signals", [])],
            consensus_type=data.get("consensus_type", "majority"),
            consensus_score=data.get("consensus_score", 0.0),
            consensus_strength=SignalStrength(data["consensus_strength"]) if data.get("consensus_strength") else SignalStrength.MEDIUM,
            total_signals=data.get("total_signals", 0),
            buy_signals=data.get("buy_signals", 0),
            sell_signals=data.get("sell_signals", 0),
            hold_signals=data.get("hold_signals", 0),
            neutral_signals=data.get("neutral_signals", 0),
            weighted_confidence=data.get("weighted_confidence", 0.0),
            weighted_signal=SignalType(data["weighted_signal"]) if data.get("weighted_signal") else SignalType.NEUTRAL,
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("timestamp"):
            agg.timestamp = datetime.fromisoformat(data["timestamp"])
            
        if data.get("aggregated_signal"):
            agg.aggregated_signal = Signal.from_dict(data["aggregated_signal"])
            
        agg.__post_init__()
        return agg


# ====================================================================================
# SIGNAL FILTER MODELS
# ====================================================================================

@dataclass
class SignalFilter:
    """
    Filter for trading signals.
    """
    # Core filters
    types: List[SignalType] = field(default_factory=list)
    sources: List[SignalSource] = field(default_factory=list)
    strengths: List[SignalStrength] = field(default_factory=list)
    statuses: List[SignalStatus] = field(default_factory=list)
    priorities: List[SignalPriority] = field(default_factory=list)
    
    # Symbol filters
    symbols: List[str] = field(default_factory=list)
    exchanges: List[str] = field(default_factory=list)
    
    # Confidence filters
    min_confidence: float = 0.0
    max_confidence: float = 1.0
    
    # Time filters
    generated_since: Optional[datetime] = None
    generated_until: Optional[datetime] = None
    expires_after: Optional[datetime] = None
    expires_before: Optional[datetime] = None
    
    # Performance filters
    min_performance_score: float = -1.0
    max_performance_score: float = 1.0
    min_historical_accuracy: float = 0.0
    max_historical_accuracy: float = 1.0
    
    # Pagination
    limit: int = 100
    offset: int = 0
    
    # Sorting
    sort_by: str = "generated_at"
    sort_order: str = "desc"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "types": [t.value for t in self.types],
            "sources": [s.value for s in self.sources],
            "strengths": [s.value for s in self.strengths],
            "statuses": [s.value for s in self.statuses],
            "priorities": [p.value for p in self.priorities],
            "symbols": self.symbols,
            "exchanges": self.exchanges,
            "min_confidence": self.min_confidence,
            "max_confidence": self.max_confidence,
            "generated_since": self.generated_since.isoformat() if self.generated_since else None,
            "generated_until": self.generated_until.isoformat() if self.generated_until else None,
            "expires_after": self.expires_after.isoformat() if self.expires_after else None,
            "expires_before": self.expires_before.isoformat() if self.expires_before else None,
            "min_performance_score": self.min_performance_score,
            "max_performance_score": self.max_performance_score,
            "min_historical_accuracy": self.min_historical_accuracy,
            "max_historical_accuracy": self.max_historical_accuracy,
            "limit": self.limit,
            "offset": self.offset,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order
        }


# ====================================================================================
# SIGNAL PERFORMANCE MODELS
# ====================================================================================

@dataclass
class SignalPerformance:
    """
    Performance tracking for signals.
    """
    # Core fields
    signal_id: str = ""
    symbol: str = ""
    exchange: str = ""
    
    # Performance metrics
    total_signals: int = 0
    successful_signals: int = 0
    failed_signals: int = 0
    win_rate: float = 0.0
    
    # Profit metrics
    total_profit: float = 0.0
    avg_profit: float = 0.0
    max_profit: float = 0.0
    min_profit: float = 0.0
    
    # Risk metrics
    avg_risk: float = 0.0
    risk_reward_ratio: float = 0.0
    sharpe_ratio: float = 0.0
    
    # By signal type
    performance_by_type: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    performance_by_source: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    performance_by_strength: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Time-based metrics
    avg_time_to_execution: float = 0.0    # seconds
    avg_time_to_profit: float = 0.0      # seconds
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "total_signals": self.total_signals,
            "successful_signals": self.successful_signals,
            "failed_signals": self.failed_signals,
            "win_rate": self.win_rate,
            "total_profit": self.total_profit,
            "avg_profit": self.avg_profit,
            "max_profit": self.max_profit,
            "min_profit": self.min_profit,
            "avg_risk": self.avg_risk,
            "risk_reward_ratio": self.risk_reward_ratio,
            "sharpe_ratio": self.sharpe_ratio,
            "performance_by_type": self.performance_by_type,
            "performance_by_source": self.performance_by_source,
            "performance_by_strength": self.performance_by_strength,
            "avg_time_to_execution": self.avg_time_to_execution,
            "avg_time_to_profit": self.avg_time_to_profit,
            "metadata": self.metadata
        }
        
    def update(self, signal: Signal, profit: float, risk: float) -> None:
        """
        Update performance with a signal result.
        
        Args:
            signal: Signal object
            profit: Profit/loss from signal
            risk: Risk taken
        """
        self.total_signals += 1
        
        if profit > 0:
            self.successful_signals += 1
        else:
            self.failed_signals += 1
            
        self.win_rate = (self.successful_signals / self.total_signals) * 100
        
        self.total_profit += profit
        self.avg_profit = self.total_profit / self.total_signals
        self.max_profit = max(self.max_profit, profit)
        self.min_profit = min(self.min_profit, profit)
        
        self.avg_risk = (self.avg_risk * (self.total_signals - 1) + risk) / self.total_signals
        self.risk_reward_ratio = (self.avg_profit / self.avg_risk) if self.avg_risk > 0 else 0
        
        # Update by type
        signal_type = signal.type.value
        if signal_type not in self.performance_by_type:
            self.performance_by_type[signal_type] = {
                "total": 0, "successful": 0, "profit": 0.0
            }
        self.performance_by_type[signal_type]["total"] += 1
        if profit > 0:
            self.performance_by_type[signal_type]["successful"] += 1
        self.performance_by_type[signal_type]["profit"] += profit
        
        # Update by source
        signal_source = signal.source.value
        if signal_source not in self.performance_by_source:
            self.performance_by_source[signal_source] = {
                "total": 0, "successful": 0, "profit": 0.0
            }
        self.performance_by_source[signal_source]["total"] += 1
        if profit > 0:
            self.performance_by_source[signal_source]["successful"] += 1
        self.performance_by_source[signal_source]["profit"] += profit


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_signal_confidence(
    indicators: List[float],
    weights: Optional[List[float]] = None
) -> float:
    """
    Calculate signal confidence from multiple indicators.
    
    Args:
        indicators: List of indicator values (0-1)
        weights: List of weights for each indicator
        
    Returns:
        Confidence score (0-1)
    """
    if not indicators:
        return 0.0
        
    if weights is None:
        weights = [1.0] * len(indicators)
        
    if len(indicators) != len(weights):
        raise ValueError("Indicators and weights must have same length")
        
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
        
    weighted_sum = sum(i * w for i, w in zip(indicators, weights))
    return weighted_sum / total_weight


def combine_signals(
    signals: List[Signal],
    method: str = "weighted"
) -> Optional[Signal]:
    """
    Combine multiple signals into one.
    
    Args:
        signals: List of signals
        method: Combination method (weighted, majority, max)
        
    Returns:
        Combined signal or None
    """
    if not signals:
        return None
        
    if method == "weighted":
        # Weighted average based on confidence
        total_weight = sum(s.confidence for s in signals)
        if total_weight == 0:
            return None
            
        # Determine weighted signal type
        buy_weight = sum(s.confidence for s in signals if s.type == SignalType.BUY)
        sell_weight = sum(s.confidence for s in signals if s.type == SignalType.SELL)
        
        if buy_weight > sell_weight:
            signal_type = SignalType.BUY
            confidence = buy_weight / total_weight
        elif sell_weight > buy_weight:
            signal_type = SignalType.SELL
            confidence = sell_weight / total_weight
        else:
            signal_type = SignalType.HOLD
            confidence = 0.5
            
        # Create combined signal
        combined = Signal(
            type=signal_type,
            source=SignalSource.CUSTOM,
            symbol=signals[0].symbol,
            exchange=signals[0].exchange,
            confidence=confidence,
            supporting_signals=[s.signal_id for s in signals]
        )
        return combined
        
    elif method == "majority":
        # Majority vote
        buy_count = sum(1 for s in signals if s.type == SignalType.BUY)
        sell_count = sum(1 for s in signals if s.type == SignalType.SELL)
        hold_count = sum(1 for s in signals if s.type == SignalType.HOLD)
        
        if buy_count > sell_count and buy_count > hold_count:
            signal_type = SignalType.BUY
        elif sell_count > buy_count and sell_count > hold_count:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.HOLD
            
        avg_confidence = sum(s.confidence for s in signals) / len(signals)
        
        combined = Signal(
            type=signal_type,
            source=SignalSource.CUSTOM,
            symbol=signals[0].symbol,
            exchange=signals[0].exchange,
            confidence=avg_confidence,
            supporting_signals=[s.signal_id for s in signals]
        )
        return combined
        
    elif method == "max":
        # Take signal with highest confidence
        best_signal = max(signals, key=lambda s: s.confidence)
        return best_signal
        
    return None


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'SignalType',
    'SignalStrength',
    'SignalSource',
    'SignalStatus',
    'SignalPriority',
    'SignalValidationMethod',
    
    # Core Models
    'Signal',
    'SignalAggregation',
    'SignalFilter',
    'SignalPerformance',
    
    # Helper Functions
    'calculate_signal_confidence',
    'combine_signals',
]
