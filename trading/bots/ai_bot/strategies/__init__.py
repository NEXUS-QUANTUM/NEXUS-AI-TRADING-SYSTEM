# trading/bots/ai_bot/strategies/__init__.py
# NEXUS AI TRADING SYSTEM - Trading Strategies Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Trading Strategies Module for NEXUS AI Trading Bot.

This module provides comprehensive trading strategies including:
- Base strategy framework
- Trend Following Strategy
- Momentum Strategy
- Mean Reversion Strategy
- Breakout Strategy
- Scalping Strategy
- Grid Trading Strategy
- Arbitrage Strategy
- Reinforcement Learning Strategy
- Hybrid Strategy
- Strategy Factory
- Strategy Executor
- Strategy Selector
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

# Version
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Module logger
logger = logging.getLogger("nexus.trading.strategies")

# ============================================================================
# Base Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.base_strategy import (
    BaseStrategy,
    StrategyConfig,
    StrategyState,
    StrategyType,
    Signal,
    SignalType,
    SignalStrength,
    Position,
    StrategyMetrics,
)

# ============================================================================
# Trend Following Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.trend_following_strategy import (
    TrendFollowingStrategy,
    TrendFollowingConfig,
    TrendType,
    TrendStrength,
    TrendSignal,
    create_trend_following_strategy,
)

# ============================================================================
# Momentum Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.momentum_strategy import (
    MomentumStrategy,
    MomentumConfig,
    MomentumType,
    MomentumDirection,
    DivergenceType,
    MomentumSignal,
    create_momentum_strategy,
)

# ============================================================================
# Mean Reversion Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.mean_reversion_strategy import (
    MeanReversionStrategy,
    MeanReversionConfig,
    ReversionType,
    ReversionState,
    ReversionSignal,
    create_mean_reversion_strategy,
)

# ============================================================================
# Breakout Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.breakout_strategy import (
    BreakoutStrategy,
    BreakoutConfig,
    BreakoutType,
    BreakoutDirection,
    BreakoutConfidence,
    BreakoutLevel,
    BreakoutSignal,
    create_breakout_strategy,
)

# ============================================================================
# Scalping Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.scalping_strategy import (
    ScalpingStrategy,
    ScalpingConfig,
    ScalpingSignal,
    create_scalping_strategy,
)

# ============================================================================
# Grid Trading Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.grid_trading_strategy import (
    GridTradingStrategy,
    GridTradingConfig,
    GridType,
    GridLevel,
    GridOrder,
    GridPosition,
    create_grid_trading_strategy,
)

# ============================================================================
# Arbitrage Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.arbitrage_strategy import (
    ArbitrageStrategy,
    ArbitrageConfig,
    ArbitrageType,
    ArbitrageState,
    ArbitrageOpportunity,
    ExchangePrice,
    create_arbitrage_strategy,
)

# ============================================================================
# Reinforcement Learning Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.reinforcement_strategy import (
    ReinforcementStrategy,
    RLConfig,
    RLAlgorithm,
    ActionType,
    Experience,
    ReplayBuffer,
    DQNNetwork,
    DuelingDQNNetwork,
    PPONetwork,
    create_reinforcement_strategy,
)

# ============================================================================
# Hybrid Strategy
# ============================================================================

from trading.bots.ai_bot.strategies.hybrid_strategy import (
    HybridStrategy,
    HybridConfig,
    MarketRegime,
    WeightingMethod,
    StrategyWeight,
    EnsembleSignal,
    create_hybrid_strategy,
)

# ============================================================================
# Strategy Factory
# ============================================================================

from trading.bots.ai_bot.strategies.strategy_factory import (
    StrategyFactory,
    StrategyCategory,
    StrategyRegistration,
    get_strategy_factory,
    create_strategy,
    list_strategies,
)

# ============================================================================
# Strategy Executor
# ============================================================================

from trading.bots.ai_bot.strategies.strategy_executor import (
    StrategyExecutor,
    ExecutorState,
    ExecutionMode,
    StrategyInstance,
    ExecutionContext,
    ExecutionResult,
    create_strategy_executor,
)

# ============================================================================
# Strategy Selector
# ============================================================================

from trading.bots.ai_bot.strategies.strategy_selector import (
    StrategySelector,
    SelectionMode,
    SelectionCriteria,
    StrategyScore,
    MarketRegime as SelectorMarketRegime,
    StrategySelection,
    create_strategy_selector,
)

# ============================================================================
# Grid Trading Strategy (Full Implementation)
# ============================================================================

# Note: GridTradingStrategy and related classes are imported above
# The full implementation is in grid_trading_strategy.py

# ============================================================================
# Scalping Strategy (Full Implementation)
# ============================================================================

# Note: ScalpingStrategy and related classes are imported above
# The full implementation is in scalping_strategy.py

# ============================================================================
# Module Information
# ============================================================================

MODULE_INFO = {
    "name": "Trading Strategies",
    "version": __version__,
    "author": __author__,
    "copyright": __copyright__,
    "description": "Comprehensive trading strategies for NEXUS AI Trading Bot",
    "strategies": [
        "Base Strategy",
        "Trend Following",
        "Momentum",
        "Mean Reversion",
        "Breakout",
        "Scalping",
        "Grid Trading",
        "Arbitrage",
        "Reinforcement Learning",
        "Hybrid",
    ],
    "features": [
        "Strategy lifecycle management",
        "Signal generation and processing",
        "Risk management integration",
        "Performance tracking",
        "Market regime detection",
        "Adaptive strategy selection",
        "Multi-strategy orchestration",
        "Ensemble strategies",
        "AI/ML integration",
        "Backtesting support",
    ],
    "strategy_categories": {
        "trending": ["Trend Following", "Momentum"],
        "mean_reversion": ["Mean Reversion"],
        "breakout": ["Breakout"],
        "scalping": ["Scalping"],
        "grid": ["Grid Trading"],
        "arbitrage": ["Arbitrage"],
        "reinforcement": ["Reinforcement Learning"],
        "hybrid": ["Hybrid"],
    },
}


def get_module_info() -> Dict[str, Any]:
    """Get module information."""
    return MODULE_INFO


def get_version() -> str:
    """Get module version."""
    return __version__


# ============================================================================
# Module Initialization
# ============================================================================

def initialize_module(
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Initialize the trading strategies module.

    Args:
        config: Configuration dictionary for the module

    Returns:
        Dictionary containing initialized components
    """
    logger.info("Initializing Trading Strategies Module...")

    config = config or {}

    # Components that will be initialized
    components = {}

    try:
        # Initialize strategy factory
        components["factory"] = get_strategy_factory()

        # Initialize strategy selector
        if config.get("market_data_provider"):
            components["selector"] = create_strategy_selector(
                market_data_provider=config["market_data_provider"],
                config=config.get("selector_config", {}),
            )

        # Initialize strategy executor
        if config.get("order_manager") and config.get("risk_manager"):
            components["executor"] = create_strategy_executor(
                order_manager=config["order_manager"],
                risk_manager=config["risk_manager"],
                market_data_provider=config.get("market_data_provider"),
                config=config.get("executor_config", {}),
            )

        logger.info("Trading Strategies Module initialized successfully")
        logger.info(f"  - Available Strategies: {len(list_strategies())}")
        logger.info(f"  - Strategy Categories: {len(components.get('factory', {}).get_strategy_categories() if components.get('factory') else [])}")

    except Exception as e:
        logger.error(f"Failed to initialize Trading Strategies Module: {e}")
        raise

    return components


# ============================================================================
# Quick Access Functions
# ============================================================================

def create_strategy_instance(
    name: str,
    config: Dict[str, Any],
    order_manager: Any,
    risk_manager: Any,
    market_data_provider: Any,
    **kwargs,
) -> Optional[BaseStrategy]:
    """
    Quick access function to create a strategy instance.

    Args:
        name: Strategy name
        config: Strategy configuration
        order_manager: Order management instance
        risk_manager: Risk management instance
        market_data_provider: Market data provider
        **kwargs: Additional arguments

    Returns:
        Strategy instance or None
    """
    return create_strategy(
        name=name,
        config=config,
        order_manager=order_manager,
        risk_manager=risk_manager,
        market_data_provider=market_data_provider,
        **kwargs,
    )


def get_available_strategies() -> Dict[str, str]:
    """
    Get available strategies with descriptions.

    Returns:
        Dict of strategy name -> description
    """
    factory = get_strategy_factory()
    strategies = {}

    for name in factory.get_strategy_names():
        doc = factory.get_strategy_documentation(name)
        if doc:
            strategies[name] = doc.get("description", "")

    return strategies


def get_strategy_categories() -> Dict[str, List[str]]:
    """
    Get strategies grouped by category.

    Returns:
        Dict of category -> list of strategy names
    """
    factory = get_strategy_factory()
    categories = {}

    for registration in factory.get_strategies():
        category = registration.category.value
        if category not in categories:
            categories[category] = []
        categories[category].append(registration.name)

    return categories


def get_strategy_names_by_category(category: str) -> List[str]:
    """
    Get strategy names by category.

    Args:
        category: Strategy category

    Returns:
        List of strategy names
    """
    factory = get_strategy_factory()
    strategies = []

    for registration in factory.get_strategies():
        if registration.category.value == category:
            strategies.append(registration.name)

    return strategies


def get_strategy_class(name: str) -> Optional[Any]:
    """
    Get strategy class by name.

    Args:
        name: Strategy name

    Returns:
        Strategy class or None
    """
    factory = get_strategy_factory()
    return factory.get_strategy_class(name)


def get_config_class(name: str) -> Optional[Any]:
    """
    Get config class by name.

    Args:
        name: Strategy name

    Returns:
        Config class or None
    """
    factory = get_strategy_factory()
    return factory.get_config_class(name)


# ============================================================================
# Strategy Registration Helpers
# ============================================================================

def register_custom_strategy(
    name: str,
    strategy_class: Any,
    config_class: Any,
    category: str = "custom",
    version: str = "1.0.0",
    description: str = "",
    tags: Optional[List[str]] = None,
) -> bool:
    """
    Register a custom strategy.

    Args:
        name: Strategy name
        strategy_class: Strategy class
        config_class: Config class
        category: Strategy category
        version: Strategy version
        description: Strategy description
        tags: Strategy tags

    Returns:
        True if registered successfully
    """
    factory = get_strategy_factory()

    return factory.register_strategy(
        name=name,
        category=StrategyCategory(category),
        strategy_class=strategy_class,
        config_class=config_class,
        version=version,
        description=description,
        tags=tags,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Print module info
    print(f"Trading Strategies Module v{__version__}")
    print(f"Author: {__author__}")
    print(f"\nAvailable Strategies:")
    for name, description in get_available_strategies().items():
        print(f"  - {name}: {description}")

    print(f"\nStrategy Categories:")
    for category, strategies in get_strategy_categories().items():
        print(f"  - {category}: {', '.join(strategies)}")

    print(f"\nModule Features:")
    for feature in MODULE_INFO["features"]:
        print(f"  - {feature}")
