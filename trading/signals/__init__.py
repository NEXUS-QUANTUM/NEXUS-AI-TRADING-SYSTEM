# trading/signals/__init__.py
"""
NEXUS AI TRADING SYSTEM - Signals Package
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This package provides comprehensive signal generation, processing,
and management capabilities for the NEXUS AI Trading System. It includes
signal generation, filtering, confidence scoring, aggregation, real-time
processing, storage, backtesting, and optimization.

Package Structure:
    - base.py: Core signal definitions and data models
    - generator.py: Signal generation from various sources
    - filter.py: Advanced signal filtering and validation
    - confidence.py: Confidence scoring and calibration
    - aggregator.py: Multi-strategy signal aggregation
    - realtime.py: Real-time signal processing
    - storage.py: Persistent signal storage
    - optimizer.py: Signal optimization and tuning
    - backtest.py: Signal backtesting and validation
    - validator.py: Signal validation and quality checks

Key Features:
    - Multi-source signal generation
    - Advanced filtering and validation
    - Confidence scoring and calibration
    - Real-time processing
    - Persistent storage
    - Backtesting and validation
    - Performance tracking
"""

import logging
from typing import Dict, List, Optional, Type, Union, Any

# ============================================================================
# Version
# ============================================================================

__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"


# ============================================================================
# Setup Logging
# ============================================================================

logger = logging.getLogger(__name__)


# ============================================================================
# Package Exports
# ============================================================================

# Base signal definitions
from .base import (
    Signal,
    SignalType,
    SignalStrength,
    SignalSource,
    SignalFactory,
    SignalValidator,
)

# Signal generation
from .generator import (
    SignalGenerator,
    SignalGeneratorConfig,
    GeneratedSignal,
    SignalGenerationMethod,
    PatternType,
)

# Signal filtering
from .filter import (
    SignalFilter,
    SignalFilterConfig,
    FilterCondition,
    FilterType,
    FilterOperator,
    FilterResult,
)

# Confidence scoring
from .confidence import (
    ConfidenceScoringEngine,
    ConfidenceConfig,
    ConfidenceResult,
    ConfidenceFactor,
    HistoricalPerformance,
)

# Signal aggregation
from .aggregator import (
    SignalAggregator,
    AggregatorConfig,
    AggregatedSignal,
    AggregationMethod,
    ConflictResolution,
    AggregationStats,
)

# Real-time processing
from .realtime import (
    RealtimeSignalProcessor,
    SignalEnvelope,
    SignalPriority,
    SignalConflictResolution,
    SignalAggregation,
)

# Signal storage
from .storage import (
    SignalStorage,
    SignalStorageManager,
    SignalRecord,
    SignalStatus,
    SignalOutcome,
)

# Signal optimization
from .optimizer import (
    SignalOptimizer,
    SignalOptimizerConfig,
    OptimizedSignal,
    OptimizationMetric,
    SignalFilterType,
    SignalPerformance,
)

# Signal backtesting
from .backtest import (
    SignalBacktestEngine,
    BacktestConfig,
    BacktestResult,
    BacktestMode,
    SignalExecutionType,
)

# Signal validation
from .validator import (
    SignalValidator as Validator,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)


# ============================================================================
# Package Initialization
# ============================================================================

def initialize(
    db_path: Optional[str] = None,
    enable_storage: bool = True,
    enable_realtime: bool = True,
) -> Dict[str, Any]:
    """
    Initialize the signals package.
    
    Args:
        db_path: Database path for signal storage
        enable_storage: Enable signal storage
        enable_realtime: Enable real-time processing
        
    Returns:
        Dict[str, Any]: Initialized components
    """
    components = {}
    
    # Initialize storage
    if enable_storage:
        storage = SignalStorage(db_path or "data/signals.db")
        components["storage"] = storage
    
    # Initialize signal generator
    generator = SignalGenerator()
    components["generator"] = generator
    
    # Initialize confidence engine
    confidence_engine = ConfidenceScoringEngine()
    components["confidence_engine"] = confidence_engine
    
    # Initialize signal filter
    signal_filter = SignalFilter()
    components["signal_filter"] = signal_filter
    
    # Initialize aggregator
    aggregator = SignalAggregator(confidence_engine=confidence_engine)
    components["aggregator"] = aggregator
    
    # Initialize real-time processor
    if enable_realtime:
        processor = RealtimeSignalProcessor(
            signal_storage=storage if enable_storage else None,
        )
        components["processor"] = processor
    
    # Initialize optimizer
    optimizer = SignalOptimizer(signal_storage=storage if enable_storage else None)
    components["optimizer"] = optimizer
    
    # Initialize backtest engine
    backtest_engine = SignalBacktestEngine(
        signal_storage=storage if enable_storage else None,
        confidence_engine=confidence_engine,
        signal_filter=signal_filter,
    )
    components["backtest_engine"] = backtest_engine
    
    logger.info("Signals package initialized successfully")
    return components


# ============================================================================
# Convenience Functions
# ============================================================================

def create_signal(
    symbol: str,
    signal_type: Union[str, SignalType],
    confidence: float = 0.5,
    strength: Union[str, SignalStrength] = SignalStrength.MEDIUM,
    price: float = 0.0,
    position_size: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    source: Union[str, SignalSource] = SignalSource.STRATEGY,
    strategy_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    priority: int = 5,
) -> Signal:
    """
    Convenience function to create a trading signal.
    
    Args:
        symbol: Trading symbol
        signal_type: Signal type (BUY/SELL/CLOSE/NEUTRAL/HOLD)
        confidence: Confidence level (0-1)
        strength: Signal strength
        price: Signal price
        position_size: Position size
        stop_loss: Stop loss price
        take_profit: Take profit price
        source: Signal source
        strategy_id: Strategy ID
        metadata: Additional metadata
        tags: Signal tags
        priority: Signal priority
        
    Returns:
        Signal: Created signal
    """
    if isinstance(signal_type, str):
        signal_type = SignalType(signal_type.lower())
    
    if isinstance(strength, str):
        strength = SignalStrength(strength.lower())
    
    if isinstance(source, str):
        source = SignalSource(source.lower())
    
    return Signal(
        symbol=symbol,
        signal_type=signal_type,
        confidence=confidence,
        strength=strength,
        price=price,
        position_size=position_size,
        stop_loss=stop_loss,
        take_profit=take_profit,
        source=source,
        strategy_id=strategy_id,
        metadata=metadata or {},
        tags=tags or [],
        priority=priority,
    )


def create_buy_signal(
    symbol: str,
    price: float,
    confidence: float = 0.6,
    strength: Union[str, SignalStrength] = SignalStrength.MEDIUM,
    position_size: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    **kwargs,
) -> Signal:
    """Create a BUY signal."""
    return SignalFactory.create_buy(
        symbol=symbol,
        price=price,
        confidence=confidence,
        strength=strength,
        position_size=position_size,
        stop_loss=stop_loss,
        take_profit=take_profit,
        **kwargs,
    )


def create_sell_signal(
    symbol: str,
    price: float,
    confidence: float = 0.6,
    strength: Union[str, SignalStrength] = SignalStrength.MEDIUM,
    position_size: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    **kwargs,
) -> Signal:
    """Create a SELL signal."""
    return SignalFactory.create_sell(
        symbol=symbol,
        price=price,
        confidence=confidence,
        strength=strength,
        position_size=position_size,
        stop_loss=stop_loss,
        take_profit=take_profit,
        **kwargs,
    )


def create_close_signal(
    symbol: str,
    price: float,
    confidence: float = 0.8,
    **kwargs,
) -> Signal:
    """Create a CLOSE signal."""
    return SignalFactory.create_close(
        symbol=symbol,
        price=price,
        confidence=confidence,
        **kwargs,
    )


def is_quality_signal(signal: Signal, min_confidence: float = 0.5) -> bool:
    """
    Check if a signal meets quality standards.
    
    Args:
        signal: Signal to check
        min_confidence: Minimum confidence threshold
        
    Returns:
        bool: True if signal meets quality standards
    """
    return SignalValidator.is_quality_signal(signal, min_confidence)


def get_signal_quality_score(signal: Signal) -> float:
    """
    Calculate quality score for a signal.
    
    Args:
        signal: Signal to score
        
    Returns:
        float: Quality score (0-1)
    """
    return SignalValidator.get_quality_score(signal)


# ============================================================================
# Convenience Aliases
# ============================================================================

# Signal types
BUY = SignalType.BUY
SELL = SignalType.SELL
CLOSE = SignalType.CLOSE
NEUTRAL = SignalType.NEUTRAL
HOLD = SignalType.HOLD

# Signal strengths
WEAK = SignalStrength.WEAK
MEDIUM = SignalStrength.MEDIUM
STRONG = SignalStrength.STRONG
VERY_STRONG = SignalStrength.VERY_STRONG

# Signal sources
STRATEGY = SignalSource.STRATEGY
INDICATOR = SignalSource.INDICATOR
PATTERN = SignalSource.PATTERN
AI = SignalSource.AI
MANUAL = SignalSource.MANUAL
EXTERNAL = SignalSource.EXTERNAL

# Signal priorities
CRITICAL = SignalPriority.CRITICAL
HIGH = SignalPriority.HIGH
MEDIUM_PRIORITY = SignalPriority.MEDIUM
LOW = SignalPriority.LOW
BACKGROUND = SignalPriority.BACKGROUND

# Signal status
GENERATED = SignalStatus.GENERATED
VALIDATED = SignalStatus.VALIDATED
EXECUTED = SignalStatus.EXECUTED
REJECTED = SignalStatus.REJECTED
EXPIRED = SignalStatus.EXPIRED
CLOSED = SignalStatus.CLOSED
ARCHIVED = SignalStatus.ARCHIVED

# Signal outcomes
PENDING = SignalOutcome.PENDING
PROFIT = SignalOutcome.PROFIT
LOSS = SignalOutcome.LOSS
BREAK_EVEN = SignalOutcome.BREAK_EVEN
PARTIAL = SignalOutcome.PARTIAL

# Aggregation methods
WEIGHTED_AVERAGE = AggregationMethod.WEIGHTED_AVERAGE
MAJORITY_VOTE = AggregationMethod.MAJORITY_VOTE
CONSENSUS = AggregationMethod.CONSENSUS
MAX_CONFIDENCE = AggregationMethod.MAXIMUM_CONFIDENCE
MIN_CONFIDENCE = AggregationMethod.MINIMUM_CONFIDENCE
MEDIAN = AggregationMethod.MEDIAN
DEMOCRATIC = AggregationMethod.DEMOCRATIC
ADAPTIVE = AggregationMethod.ADAPTIVE

# Filter types
CONFIDENCE_FILTER = FilterType.CONFIDENCE
VOLATILITY_FILTER = FilterType.VOLATILITY
TREND_FILTER = FilterType.TREND
MOMENTUM_FILTER = FilterType.MOMENTUM
VOLUME_FILTER = FilterType.VOLUME
SPREAD_FILTER = FilterType.SPREAD
TIME_FILTER = FilterType.TIME
PRICE_FILTER = FilterType.PRICE

# Conflict resolutions
HIGHEST_CONFIDENCE = ConflictResolution.HIGHEST_CONFIDENCE
HIGHEST_PRIORITY = ConflictResolution.HIGHEST_PRIORITY
MAJORITY = ConflictResolution.MAJORITY
WEIGHTED_VOTE = ConflictResolution.WEIGHTED_VOTE
AGGRESSIVE = ConflictResolution.AGGRESSIVE
CONSERVATIVE = ConflictResolution.CONSERVATIVE
NEUTRAL_RESOLUTION = ConflictResolution.NEUTRAL
REJECT_ALL = ConflictResolution.REJECT_ALL

# Confidence factors
HISTORICAL_ACCURACY = ConfidenceFactor.HISTORICAL_ACCURACY
MARKET_CONDITION = ConfidenceFactor.MARKET_CONDITION
INDICATOR_STRENGTH = ConfidenceFactor.INDICATOR_STRENGTH
MULTIPLE_CONFIRMATIONS = ConfidenceFactor.MULTIPLE_CONFIRMATIONS
VOLATILITY_ADJUSTMENT = ConfidenceFactor.VOLATILITY_ADJUSTMENT
TREND_ALIGNMENT = ConfidenceFactor.TREND_ALIGNMENT
VOLUME_CONFIRMATION = ConfidenceFactor.VOLUME_CONFIRMATION
TIME_DECAY = ConfidenceFactor.TIME_DECAY
STRATEGY_PERFORMANCE = ConfidenceFactor.STRATEGY_PERFORMANCE
ENSEMBLE_AGREEMENT = ConfidenceFactor.ENSEMBLE_AGREEMENT
RISK_ADJUSTMENT = ConfidenceFactor.RISK_ADJUSTMENT

# Generation methods
RULE_BASED = SignalGenerationMethod.RULE_BASED
PATTERN_GEN = SignalGenerationMethod.PATTERN
INDICATOR_GEN = SignalGenerationMethod.INDICATOR
PRICE_ACTION = SignalGenerationMethod.PRICE_ACTION
VOLUME_GEN = SignalGenerationMethod.VOLUME
ORDER_BOOK_GEN = SignalGenerationMethod.ORDER_BOOK
MULTI_TIMEFRAME = SignalGenerationMethod.MULTI_TIMEFRAME
COMPOSITE = SignalGenerationMethod.COMPOSITE

# Filter operators
GT = FilterOperator.GT
LT = FilterOperator.LT
EQ = FilterOperator.EQ
GTE = FilterOperator.GTE
LTE = FilterOperator.LTE
BETWEEN = FilterOperator.BETWEEN
IN = FilterOperator.IN
NOT_IN = FilterOperator.NOT_IN
CROSS_ABOVE = FilterOperator.CROSS_ABOVE
CROSS_BELOW = FilterOperator.CROSS_BELOW

# Backtest modes
WALK_FORWARD = BacktestMode.WALK_FORWARD
ROLLING = BacktestMode.ROLLING
EXPANDING = BacktestMode.EXPANDING
FIXED = BacktestMode.FIXED

# Signal execution types
MARKET_ORDER = SignalExecutionType.MARKET_ORDER
LIMIT_ORDER = SignalExecutionType.LIMIT_ORDER
VWAP = SignalExecutionType.VWAP
TWAP = SignalExecutionType.TWAP
IMMEDIATE = SignalExecutionType.IMMEDIATE

# Optimization metrics
SHARPE_RATIO = OptimizationMetric.SHARPE_RATIO
WIN_RATE = OptimizationMetric.WIN_RATE
PROFIT_FACTOR = OptimizationMetric.PROFIT_FACTOR
EXPECTED_VALUE = OptimizationMetric.EXPECTED_VALUE
CALMAR_RATIO = OptimizationMetric.CALMAR_RATIO
SORTINO_RATIO = OptimizationMetric.SORTINO_RATIO
MAX_DRAWDOWN = OptimizationMetric.MAX_DRAWDOWN
COMBINED_METRIC = OptimizationMetric.COMBINED


# ============================================================================
# Package Documentation
# ============================================================================

__doc__ = """
NEXUS AI Trading System - Signals Package
=========================================

A comprehensive signal processing framework for algorithmic trading.

Quick Start:
------------
    from trading.signals import (
        initialize,
        create_signal,
        BUY,
        STRONG,
        RealtimeSignalProcessor,
        SignalStorage,
    )
    
    # Initialize signals system
    components = initialize()
    
    # Create a signal
    signal = create_signal(
        symbol="BTC/USD",
        signal_type=BUY,
        confidence=0.8,
        strength=STRONG,
        price=45000.0,
        stop_loss=44000.0,
        take_profit=47000.0,
    )
    
    # Process signal in real-time
    processor = components["processor"]
    envelope = await processor.process_signal(
        signal=signal,
        strategy_id="my_strategy",
        strategy_name="Momentum Strategy",
    )
    
    # Store signal
    storage = components["storage"]
    record = SignalRecord(signal=signal, strategy_id="my_strategy")
    await storage.save_signal(record)

For more information, see the documentation in each module.
"""


# ============================================================================
# Cleanup
# ============================================================================

async def cleanup() -> None:
    """Clean up all signal resources."""
    # Close any open connections
    logger.info("Signals package cleanup complete")


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Version
    "__version__",
    "__author__",
    "__copyright__",
    
    # Initialization
    "initialize",
    "cleanup",
    
    # Base
    "Signal",
    "SignalType",
    "SignalStrength",
    "SignalSource",
    "SignalFactory",
    "SignalValidator",
    
    # Generator
    "SignalGenerator",
    "SignalGeneratorConfig",
    "GeneratedSignal",
    "SignalGenerationMethod",
    "PatternType",
    
    # Filter
    "SignalFilter",
    "SignalFilterConfig",
    "FilterCondition",
    "FilterType",
    "FilterOperator",
    "FilterResult",
    
    # Confidence
    "ConfidenceScoringEngine",
    "ConfidenceConfig",
    "ConfidenceResult",
    "ConfidenceFactor",
    "HistoricalPerformance",
    
    # Aggregator
    "SignalAggregator",
    "AggregatorConfig",
    "AggregatedSignal",
    "AggregationMethod",
    "ConflictResolution",
    "AggregationStats",
    
    # Real-time
    "RealtimeSignalProcessor",
    "SignalEnvelope",
    "SignalPriority",
    "SignalConflictResolution",
    "SignalAggregation",
    
    # Storage
    "SignalStorage",
    "SignalStorageManager",
    "SignalRecord",
    "SignalStatus",
    "SignalOutcome",
    
    # Optimizer
    "SignalOptimizer",
    "SignalOptimizerConfig",
    "OptimizedSignal",
    "OptimizationMetric",
    "SignalFilterType",
    "SignalPerformance",
    
    # Backtest
    "SignalBacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "BacktestMode",
    "SignalExecutionType",
    
    # Validator
    "Validator",
    "ValidationResult",
    "ValidationRule",
    "ValidationSeverity",
    
    # Convenience functions
    "create_signal",
    "create_buy_signal",
    "create_sell_signal",
    "create_close_signal",
    "is_quality_signal",
    "get_signal_quality_score",
    
    # Convenience aliases - Signal Types
    "BUY",
    "SELL",
    "CLOSE",
    "NEUTRAL",
    "HOLD",
    
    # Signal Strengths
    "WEAK",
    "MEDIUM",
    "STRONG",
    "VERY_STRONG",
    
    # Signal Sources
    "STRATEGY",
    "INDICATOR",
    "PATTERN",
    "AI",
    "MANUAL",
    "EXTERNAL",
    
    # Signal Priorities
    "CRITICAL",
    "HIGH",
    "MEDIUM_PRIORITY",
    "LOW",
    "BACKGROUND",
    
    # Signal Status
    "GENERATED",
    "VALIDATED",
    "EXECUTED",
    "REJECTED",
    "EXPIRED",
    "CLOSED",
    "ARCHIVED",
    
    # Signal Outcomes
    "PENDING",
    "PROFIT",
    "LOSS",
    "BREAK_EVEN",
    "PARTIAL",
    
    # Aggregation Methods
    "WEIGHTED_AVERAGE",
    "MAJORITY_VOTE",
    "CONSENSUS",
    "MAX_CONFIDENCE",
    "MIN_CONFIDENCE",
    "MEDIAN",
    "DEMOCRATIC",
    "ADAPTIVE",
    
    # Filter Types
    "CONFIDENCE_FILTER",
    "VOLATILITY_FILTER",
    "TREND_FILTER",
    "MOMENTUM_FILTER",
    "VOLUME_FILTER",
    "SPREAD_FILTER",
    "TIME_FILTER",
    "PRICE_FILTER",
    
    # Conflict Resolutions
    "HIGHEST_CONFIDENCE",
    "HIGHEST_PRIORITY",
    "MAJORITY",
    "WEIGHTED_VOTE",
    "AGGRESSIVE",
    "CONSERVATIVE",
    "NEUTRAL_RESOLUTION",
    "REJECT_ALL",
    
    # Confidence Factors
    "HISTORICAL_ACCURACY",
    "MARKET_CONDITION",
    "INDICATOR_STRENGTH",
    "MULTIPLE_CONFIRMATIONS",
    "VOLATILITY_ADJUSTMENT",
    "TREND_ALIGNMENT",
    "VOLUME_CONFIRMATION",
    "TIME_DECAY",
    "STRATEGY_PERFORMANCE",
    "ENSEMBLE_AGREEMENT",
    "RISK_ADJUSTMENT",
    
    # Generation Methods
    "RULE_BASED",
    "PATTERN_GEN",
    "INDICATOR_GEN",
    "PRICE_ACTION",
    "VOLUME_GEN",
    "ORDER_BOOK_GEN",
    "MULTI_TIMEFRAME",
    "COMPOSITE",
    
    # Filter Operators
    "GT",
    "LT",
    "EQ",
    "GTE",
    "LTE",
    "BETWEEN",
    "IN",
    "NOT_IN",
    "CROSS_ABOVE",
    "CROSS_BELOW",
    
    # Backtest
    "WALK_FORWARD",
    "ROLLING",
    "EXPANDING",
    "FIXED",
    "MARKET_ORDER",
    "LIMIT_ORDER",
    "VWAP",
    "TWAP",
    "IMMEDIATE",
    
    # Optimization
    "SHARPE_RATIO",
    "WIN_RATE",
    "PROFIT_FACTOR",
    "EXPECTED_VALUE",
    "CALMAR_RATIO",
    "SORTINO_RATIO",
    "MAX_DRAWDOWN",
    "COMBINED_METRIC",
]
