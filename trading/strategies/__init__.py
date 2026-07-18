# trading/strategies/__init__.py
"""
NEXUS AI TRADING SYSTEM - Strategies Package
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This package provides comprehensive trading strategy implementations for the
NEXUS AI Trading System. It includes both traditional and AI-powered strategies
with a unified interface for signal generation, position management, and
performance tracking.

Package Structure:
    - base.py: Abstract base strategy class
    - factory.py: Strategy factory and registry
    - parameters.py: Parameter management and optimization
    
    - ai_ensemble.py: AI ensemble strategy with multiple models
    - arbitrage.py: Arbitrage trading strategies
    - breakout.py: Breakout and channel strategies
    - custom.py: Custom rule-based strategies
    - grid_trading.py: Grid trading strategy
    - martingale.py: Martingale progressive betting
    - mean_reversion.py: Mean reversion strategies
    - momentum.py: Momentum trading strategies
    - pairs_trading.py: Pairs trading strategies
    - scalping.py: High-frequency scalping strategies

Key Features:
    - Unified strategy interface
    - Signal generation and management
    - Position and risk management
    - Performance tracking and metrics
    - Strategy parameter optimization
    - Backtesting support
    - Real-time trading support
"""

import logging
from typing import Dict, List, Optional, Type, Union

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

# Base classes
from .base import (
    BaseStrategy,
    StrategyConfig,
    StrategyType,
    StrategyState,
    Signal,
    SignalType,
    SignalStrength,
    StrategyMetrics,
)

# Factory
from .factory import (
    StrategyFactory,
    StrategyRegistry,
    StrategyCache,
    StrategyMetadata,
    create_strategy,
    create_strategy_async,
)

# Parameters
from .parameters import (
    ParameterManager,
    ParameterSet,
    ParameterDefinition,
    ParameterType,
    ParameterScope,
    ParameterOptimizer,
    StrategyParameterSchema,
)

# AI Ensemble
from .ai_ensemble import (
    AIEnsembleStrategy,
    EnsembleConfig,
    EnsembleMethod,
    ModelWeightStrategy,
    ModelPerformance,
    EnsemblePrediction,
)

# Arbitrage
from .arbitrage import (
    ArbitrageStrategy,
    ArbitrageConfig,
    ArbitrageType,
    ArbitrageOpportunity,
    StatisticalArbitrageMethod,
)

# Breakout
from .breakout import (
    BreakoutStrategy,
    BreakoutConfig,
    BreakoutType,
    BreakoutConfirmation,
    BreakoutLevel,
    BreakoutSignal,
)

# Custom
from .custom import (
    CustomStrategy,
    CustomStrategyConfig,
    Condition,
    ConditionOperator,
    ConditionType,
    Action,
    ActionType,
    Rule,
    IndicatorConfig,
)

# Grid Trading
from .grid_trading import (
    GridTradingStrategy,
    GridConfig,
    GridType,
    GridLevel,
    GridState,
    GridOrderStatus,
)

# Martingale
from .martingale import (
    MartingaleStrategy,
    MartingaleConfig,
    MartingaleType,
    MartingaleDirection,
    MartingaleState,
)

# Mean Reversion
from .mean_reversion import (
    MeanReversionStrategy,
    MeanReversionConfig,
    ReversionType,
    EntryTrigger,
    MeanReversionState,
)

# Momentum
from .momentum import (
    MomentumStrategy,
    MomentumConfig,
    MomentumType,
    MomentumDirection,
    MomentumState,
)

# Pairs Trading
from .pairs_trading import (
    PairsTradingStrategy,
    PairsConfig,
    PairSelectionMethod,
    TradingPair,
    PairsState,
    PairTradingSignal,
)

# Scalping
from .scalping import (
    ScalpingStrategy,
    ScalpingConfig,
    ScalpingType,
    OrderBookSide,
    ScalpingState,
)


# ============================================================================
# Package Initialization
# ============================================================================

def initialize(auto_discover: bool = True) -> StrategyFactory:
    """
    Initialize the strategy system.
    
    Args:
        auto_discover: Whether to auto-discover strategy implementations
        
    Returns:
        StrategyFactory: Strategy factory instance
    """
    StrategyFactory.initialize(auto_discover=auto_discover)
    logger.info("Strategy system initialized successfully")
    return StrategyFactory


def get_available_strategies() -> List[Dict[str, any]]:
    """
    Get list of all available strategies.
    
    Returns:
        List[Dict[str, any]]: List of strategy information
    """
    StrategyFactory.initialize()
    return StrategyFactory.list_available_strategies()


def create_strategy_from_config(
    config: Union[Dict[str, any], str],
    **kwargs,
) -> BaseStrategy:
    """
    Create a strategy from configuration.
    
    Args:
        config: Strategy configuration (dict or config name)
        **kwargs: Additional parameters
        
    Returns:
        BaseStrategy: Strategy instance
    """
    StrategyFactory.initialize()
    
    if isinstance(config, str):
        # Load strategy by name with default config
        return StrategyFactory.create_strategy(
            name=config,
            config=StrategyConfig(name=config),
            extra_params=kwargs,
        )
    
    return StrategyFactory.create_from_dict(config)


async def create_strategy_from_config_async(
    config: Union[Dict[str, any], str],
    **kwargs,
) -> BaseStrategy:
    """
    Create a strategy from configuration asynchronously.
    
    Args:
        config: Strategy configuration (dict or config name)
        **kwargs: Additional parameters
        
    Returns:
        BaseStrategy: Strategy instance
    """
    StrategyFactory.initialize()
    
    if isinstance(config, str):
        return await StrategyFactory.create_strategy_async(
            name=config,
            config=StrategyConfig(name=config),
            extra_params=kwargs,
        )
    
    return await StrategyFactory.create_from_dict_async(config, **kwargs)


# ============================================================================
# Convenience Aliases
# ============================================================================

# Strategy types
TREND_FOLLOWING = StrategyType.TREND_FOLLOWING
MEAN_REVERSION = StrategyType.MEAN_REVERSION
BREAKOUT = StrategyType.BREAKOUT
ARBITRAGE = StrategyType.ARBITRAGE
SCALPING = StrategyType.SCALPING
MOMENTUM = StrategyType.MOMENTUM
GRID = StrategyType.GRID
AI_ENSEMBLE = StrategyType.AI_ENSEMBLE
MACHINE_LEARNING = StrategyType.MACHINE_LEARNING
DEEP_LEARNING = StrategyType.DEEP_LEARNING
REINFORCEMENT = StrategyType.REINFORCEMENT
SENTIMENT = StrategyType.SENTIMENT
CUSTOM = StrategyType.CUSTOM

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


# ============================================================================
# Package Documentation
# ============================================================================

__doc__ = """
NEXUS AI Trading System - Strategies Package
============================================

A comprehensive trading strategy framework for algorithmic trading.

Quick Start:
------------
    from trading.strategies import (
        initialize,
        create_strategy_from_config,
        MomentumStrategy,
        StrategyConfig,
    )
    
    # Initialize strategy system
    factory = initialize()
    
    # Create a strategy with configuration
    config = {
        "name": "momentum_strategy",
        "strategy_type": "momentum",
        "symbol": "BTC/USD",
        "timeframe": "1h",
        "params": {
            "momentum_period": 14,
            "momentum_threshold": 2.0,
        }
    }
    strategy = create_strategy_from_config(config)
    
    # Or create directly
    strategy = MomentumStrategy(
        config=StrategyConfig(
            name="momentum_strategy",
            symbol="BTC/USD",
            timeframe="1h",
        ),
        momentum_config=MomentumConfig(
            momentum_period=14,
            momentum_threshold=2.0,
        ),
    )
    
    # Generate signals
    signal = await strategy.generate_signal(market_data)

For more information, see the documentation in each module.
"""


# ============================================================================
# Cleanup
# ============================================================================

async def cleanup() -> None:
    """Clean up all strategy resources."""
    await StrategyFactory.close_all()


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
    "get_available_strategies",
    "create_strategy_from_config",
    "create_strategy_from_config_async",
    
    # Base
    "BaseStrategy",
    "StrategyConfig",
    "StrategyType",
    "StrategyState",
    "Signal",
    "SignalType",
    "SignalStrength",
    "StrategyMetrics",
    
    # Factory
    "StrategyFactory",
    "StrategyRegistry",
    "StrategyCache",
    "StrategyMetadata",
    "create_strategy",
    "create_strategy_async",
    
    # Parameters
    "ParameterManager",
    "ParameterSet",
    "ParameterDefinition",
    "ParameterType",
    "ParameterScope",
    "ParameterOptimizer",
    "StrategyParameterSchema",
    
    # AI Ensemble
    "AIEnsembleStrategy",
    "EnsembleConfig",
    "EnsembleMethod",
    "ModelWeightStrategy",
    "ModelPerformance",
    "EnsemblePrediction",
    
    # Arbitrage
    "ArbitrageStrategy",
    "ArbitrageConfig",
    "ArbitrageType",
    "ArbitrageOpportunity",
    "StatisticalArbitrageMethod",
    
    # Breakout
    "BreakoutStrategy",
    "BreakoutConfig",
    "BreakoutType",
    "BreakoutConfirmation",
    "BreakoutLevel",
    "BreakoutSignal",
    
    # Custom
    "CustomStrategy",
    "CustomStrategyConfig",
    "Condition",
    "ConditionOperator",
    "ConditionType",
    "Action",
    "ActionType",
    "Rule",
    "IndicatorConfig",
    
    # Grid Trading
    "GridTradingStrategy",
    "GridConfig",
    "GridType",
    "GridLevel",
    "GridState",
    "GridOrderStatus",
    
    # Martingale
    "MartingaleStrategy",
    "MartingaleConfig",
    "MartingaleType",
    "MartingaleDirection",
    "MartingaleState",
    
    # Mean Reversion
    "MeanReversionStrategy",
    "MeanReversionConfig",
    "ReversionType",
    "EntryTrigger",
    "MeanReversionState",
    
    # Momentum
    "MomentumStrategy",
    "MomentumConfig",
    "MomentumType",
    "MomentumDirection",
    "MomentumState",
    
    # Pairs Trading
    "PairsTradingStrategy",
    "PairsConfig",
    "PairSelectionMethod",
    "TradingPair",
    "PairsState",
    "PairTradingSignal",
    
    # Scalping
    "ScalpingStrategy",
    "ScalpingConfig",
    "ScalpingType",
    "OrderBookSide",
    "ScalpingState",
    
    # Convenience aliases
    "TREND_FOLLOWING",
    "MEAN_REVERSION",
    "BREAKOUT",
    "ARBITRAGE",
    "SCALPING",
    "MOMENTUM",
    "GRID",
    "AI_ENSEMBLE",
    "MACHINE_LEARNING",
    "DEEP_LEARNING",
    "REINFORCEMENT",
    "SENTIMENT",
    "CUSTOM",
    "BUY",
    "SELL",
    "CLOSE",
    "NEUTRAL",
    "HOLD",
    "WEAK",
    "MEDIUM",
    "STRONG",
    "VERY_STRONG",
]
