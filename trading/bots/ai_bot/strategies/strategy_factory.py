# trading/bots/ai_bot/strategies/strategy_factory.py
# NEXUS AI TRADING SYSTEM - Strategy Factory
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Strategy Factory for NEXUS AI Trading Bot.
Provides factory methods for creating and managing trading strategies including:
- Strategy creation from configuration
- Strategy registration and lookup
- Strategy dependency injection
- Strategy validation
- Strategy lifecycle management
- Multi-strategy orchestration
- Dynamic strategy loading
- Strategy versioning
"""

import importlib
import inspect
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union

# NEXUS Imports
from trading.bots.ai_bot.strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyType
from trading.bots.ai_bot.strategies.breakout_strategy import BreakoutStrategy, BreakoutConfig
from trading.bots.ai_bot.strategies.hybrid_strategy import HybridStrategy, HybridConfig
from trading.bots.ai_bot.strategies.mean_reversion_strategy import MeanReversionStrategy, MeanReversionConfig
from trading.bots.ai_bot.strategies.momentum_strategy import MomentumStrategy, MomentumConfig
from trading.bots.ai_bot.strategies.reinforcement_strategy import ReinforcementStrategy, RLConfig
from trading.bots.ai_bot.strategies.trend_following_strategy import TrendFollowingStrategy, TrendFollowingConfig
from trading.bots.ai_bot.strategies.grid_trading_strategy import GridTradingStrategy, GridTradingConfig
from trading.bots.ai_bot.strategies.scalping_strategy import ScalpingStrategy, ScalpingConfig
from trading.bots.ai_bot.strategies.arbitrage_strategy import ArbitrageStrategy, ArbitrageConfig
from trading.bots.ai_bot.execution.order_manager import OrderManager
from trading.bots.ai_bot.risk.risk_manager import RiskManager
from trading.bots.ai_bot.market_data.market_data_provider import MarketDataProvider
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.strategy.factory")


# ============================================================================
# Enums & Constants
# ============================================================================

class StrategyCategory(str, Enum):
    """Strategy categories."""
    TRENDING = "trending"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    SCALPING = "scalping"
    GRID = "grid"
    ARBITRAGE = "arbitrage"
    HYBRID = "hybrid"
    REINFORCEMENT = "reinforcement"
    CUSTOM = "custom"


@dataclass
class StrategyRegistration:
    """Strategy registration data."""
    name: str
    category: StrategyCategory
    strategy_class: Type[BaseStrategy]
    config_class: Type[StrategyConfig]
    version: str
    description: str
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Strategy Factory
# ============================================================================

class StrategyFactory:
    """
    Strategy Factory for NEXUS AI Trading Bot.
    Provides factory methods for creating and managing trading strategies.
    """

    _instance = None
    _strategies: Dict[str, StrategyRegistration] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the factory with built-in strategies."""
        self._register_builtin_strategies()

    def _register_builtin_strategies(self) -> None:
        """Register built-in strategies."""
        # Trend Following Strategy
        self.register_strategy(
            name="trend_following",
            category=StrategyCategory.TRENDING,
            strategy_class=TrendFollowingStrategy,
            config_class=TrendFollowingConfig,
            version="1.0.0",
            description="Trend following strategy using moving averages and trend indicators",
            tags=["trend", "momentum", "swing"],
        )

        # Mean Reversion Strategy
        self.register_strategy(
            name="mean_reversion",
            category=StrategyCategory.MEAN_REVERSION,
            strategy_class=MeanReversionStrategy,
            config_class=MeanReversionConfig,
            version="1.0.0",
            description="Mean reversion strategy using Bollinger Bands and RSI",
            tags=["mean_reversion", "oscillator", "range"],
        )

        # Momentum Strategy
        self.register_strategy(
            name="momentum",
            category=StrategyCategory.MOMENTUM,
            strategy_class=MomentumStrategy,
            config_class=MomentumConfig,
            version="1.0.0",
            description="Momentum strategy using ROC, RSI, MACD, and volume",
            tags=["momentum", "trend", "breakout"],
        )

        # Breakout Strategy
        self.register_strategy(
            name="breakout",
            category=StrategyCategory.BREAKOUT,
            strategy_class=BreakoutStrategy,
            config_class=BreakoutConfig,
            version="1.0.0",
            description="Breakout strategy using support/resistance and volatility",
            tags=["breakout", "support_resistance", "volatility"],
        )

        # Scalping Strategy
        self.register_strategy(
            name="scalping",
            category=StrategyCategory.SCALPING,
            strategy_class=ScalpingStrategy,
            config_class=ScalpingConfig,
            version="1.0.0",
            description="Scalping strategy for quick profits on small price movements",
            tags=["scalping", "high_frequency", "short_term"],
        )

        # Grid Trading Strategy
        self.register_strategy(
            name="grid_trading",
            category=StrategyCategory.GRID,
            strategy_class=GridTradingStrategy,
            config_class=GridTradingConfig,
            version="1.0.0",
            description="Grid trading strategy for range-bound markets",
            tags=["grid", "range", "automated"],
        )

        # Arbitrage Strategy
        self.register_strategy(
            name="arbitrage",
            category=StrategyCategory.ARBITRAGE,
            strategy_class=ArbitrageStrategy,
            config_class=ArbitrageConfig,
            version="1.0.0",
            description="Arbitrage strategy for cross-exchange and triangular opportunities",
            tags=["arbitrage", "cross_exchange", "triangular"],
        )

        # Hybrid Strategy
        self.register_strategy(
            name="hybrid",
            category=StrategyCategory.HYBRID,
            strategy_class=HybridStrategy,
            config_class=HybridConfig,
            version="1.0.0",
            description="Hybrid strategy combining multiple strategies and AI models",
            tags=["hybrid", "ensemble", "ai", "multi_strategy"],
        )

        # Reinforcement Learning Strategy
        self.register_strategy(
            name="reinforcement",
            category=StrategyCategory.REINFORCEMENT,
            strategy_class=ReinforcementStrategy,
            config_class=RLConfig,
            version="1.0.0",
            description="Reinforcement learning strategy using DQN, PPO, A2C",
            tags=["reinforcement_learning", "dqn", "ppo", "a2c", "ai"],
        )

        logger.info(f"Registered {len(self._strategies)} built-in strategies")

    # ========================================================================
    # Strategy Registration
    # ========================================================================

    def register_strategy(
        self,
        name: str,
        category: StrategyCategory,
        strategy_class: Type[BaseStrategy],
        config_class: Type[StrategyConfig],
        version: str = "1.0.0",
        description: str = "",
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        is_active: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register a new strategy.

        Args:
            name: Strategy name
            category: Strategy category
            strategy_class: Strategy class
            config_class: Configuration class
            version: Strategy version
            description: Strategy description
            tags: Strategy tags
            dependencies: Strategy dependencies
            is_active: Whether strategy is active
            metadata: Additional metadata

        Returns:
            True if registered successfully
        """
        if name in self._strategies:
            logger.warning(f"Strategy {name} already registered")
            return False

        # Validate strategy class
        if not issubclass(strategy_class, BaseStrategy):
            logger.error(f"Strategy class must inherit from BaseStrategy")
            return False

        # Validate config class
        if not issubclass(config_class, StrategyConfig):
            logger.error(f"Config class must inherit from StrategyConfig")
            return False

        registration = StrategyRegistration(
            name=name,
            category=category,
            strategy_class=strategy_class,
            config_class=config_class,
            version=version,
            description=description,
            tags=tags or [],
            dependencies=dependencies or [],
            is_active=is_active,
            metadata=metadata or {},
        )

        self._strategies[name] = registration

        logger.info(f"Strategy registered: {name} v{version}")
        return True

    def unregister_strategy(self, name: str) -> bool:
        """
        Unregister a strategy.

        Args:
            name: Strategy name

        Returns:
            True if unregistered successfully
        """
        if name not in self._strategies:
            logger.warning(f"Strategy {name} not found")
            return False

        del self._strategies[name]
        logger.info(f"Strategy unregistered: {name}")
        return True

    # ========================================================================
    # Strategy Creation
    # ========================================================================

    def create_strategy(
        self,
        name: str,
        config: Dict[str, Any],
        order_manager: OrderManager,
        risk_manager: RiskManager,
        market_data_provider: MarketDataProvider,
        **kwargs,
    ) -> Optional[BaseStrategy]:
        """
        Create a strategy instance.

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
        registration = self._strategies.get(name)

        if not registration:
            logger.error(f"Strategy {name} not registered")
            return None

        if not registration.is_active:
            logger.warning(f"Strategy {name} is inactive")
            return None

        try:
            # Create config instance
            config_instance = registration.config_class(**config)

            # Create strategy instance
            strategy = registration.strategy_class(
                config=config_instance,
                risk_manager=risk_manager,
                order_manager=order_manager,
                market_data_provider=market_data_provider,
                **kwargs,
            )

            logger.info(f"Strategy created: {name} v{registration.version}")
            return strategy

        except Exception as e:
            logger.error(f"Error creating strategy {name}: {e}")
            return None

    def create_strategy_from_config(
        self,
        config: Dict[str, Any],
        order_manager: OrderManager,
        risk_manager: RiskManager,
        market_data_provider: MarketDataProvider,
        **kwargs,
    ) -> Optional[BaseStrategy]:
        """
        Create a strategy from configuration dictionary.

        Args:
            config: Strategy configuration
            order_manager: Order management instance
            risk_manager: Risk management instance
            market_data_provider: Market data provider
            **kwargs: Additional arguments

        Returns:
            Strategy instance or None
        """
        name = config.get("name")
        if not name:
            logger.error("Strategy name not found in configuration")
            return None

        return self.create_strategy(
            name=name,
            config=config,
            order_manager=order_manager,
            risk_manager=risk_manager,
            market_data_provider=market_data_provider,
            **kwargs,
        )

    def create_strategies(
        self,
        configs: List[Dict[str, Any]],
        order_manager: OrderManager,
        risk_manager: RiskManager,
        market_data_provider: MarketDataProvider,
        **kwargs,
    ) -> Dict[str, BaseStrategy]:
        """
        Create multiple strategies from configurations.

        Args:
            configs: List of strategy configurations
            order_manager: Order management instance
            risk_manager: Risk management instance
            market_data_provider: Market data provider
            **kwargs: Additional arguments

        Returns:
            Dict of strategy name -> strategy instance
        """
        strategies = {}

        for config in configs:
            strategy = self.create_strategy_from_config(
                config=config,
                order_manager=order_manager,
                risk_manager=risk_manager,
                market_data_provider=market_data_provider,
                **kwargs,
            )

            if strategy:
                strategies[config.get("name")] = strategy

        logger.info(f"Created {len(strategies)} strategies")
        return strategies

    # ========================================================================
    # Strategy Discovery
    # ========================================================================

    def get_strategy(self, name: str) -> Optional[StrategyRegistration]:
        """
        Get strategy registration by name.

        Args:
            name: Strategy name

        Returns:
            StrategyRegistration or None
        """
        return self._strategies.get(name)

    def get_strategies(
        self,
        category: Optional[StrategyCategory] = None,
        active_only: bool = True,
    ) -> List[StrategyRegistration]:
        """
        Get all registered strategies.

        Args:
            category: Filter by category
            active_only: Only return active strategies

        Returns:
            List of StrategyRegistration
        """
        strategies = list(self._strategies.values())

        if category:
            strategies = [s for s in strategies if s.category == category]

        if active_only:
            strategies = [s for s in strategies if s.is_active]

        return strategies

    def get_strategy_names(
        self,
        category: Optional[StrategyCategory] = None,
        active_only: bool = True,
    ) -> List[str]:
        """
        Get strategy names.

        Args:
            category: Filter by category
            active_only: Only return active strategies

        Returns:
            List of strategy names
        """
        strategies = self.get_strategies(category, active_only)
        return [s.name for s in strategies]

    def get_strategy_categories(self) -> List[StrategyCategory]:
        """
        Get all strategy categories.

        Returns:
            List of StrategyCategory
        """
        categories = set()
        for registration in self._strategies.values():
            categories.add(registration.category)
        return list(categories)

    def get_strategy_count(self) -> int:
        """
        Get number of registered strategies.

        Returns:
            Strategy count
        """
        return len(self._strategies)

    # ========================================================================
    # Strategy Validation
    # ========================================================================

    def validate_strategy_config(
        self,
        name: str,
        config: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Validate strategy configuration.

        Args:
            name: Strategy name
            config: Configuration dictionary

        Returns:
            (is_valid, errors)
        """
        errors = []

        registration = self._strategies.get(name)

        if not registration:
            errors.append(f"Strategy {name} not found")
            return False, errors

        try:
            # Validate required fields
            required_fields = ["name", "type", "symbols", "timeframe", "initial_capital"]

            for field in required_fields:
                if field not in config:
                    errors.append(f"Missing required field: {field}")

            # Validate strategy-specific config
            config_instance = registration.config_class(**config)

            # Validate position size
            if config.get("max_position_size", 0) <= 0:
                errors.append("max_position_size must be greater than 0")

            if config.get("min_confidence", 0) < 0 or config.get("min_confidence", 0) > 1:
                errors.append("min_confidence must be between 0 and 1")

            # Validate risk parameters
            if config.get("risk_per_trade", 0) < 0 or config.get("risk_per_trade", 0) > 1:
                errors.append("risk_per_trade must be between 0 and 1")

            if config.get("max_drawdown", 0) < 0 or config.get("max_drawdown", 0) > 1:
                errors.append("max_drawdown must be between 0 and 1")

        except Exception as e:
            errors.append(f"Configuration validation error: {str(e)}")

        return len(errors) == 0, errors

    # ========================================================================
    # Strategy Persistence
    # ========================================================================

    def save_strategy_config(
        self,
        name: str,
        config: Dict[str, Any],
        path: Optional[Path] = None,
    ) -> bool:
        """
        Save strategy configuration to file.

        Args:
            name: Strategy name
            config: Configuration dictionary
            path: Save path (optional)

        Returns:
            True if saved successfully
        """
        if path is None:
            path = Path(f"configs/strategies/{name}.yaml")

        try:
            import yaml

            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)

            logger.info(f"Strategy config saved: {path}")
            return True

        except Exception as e:
            logger.error(f"Error saving strategy config: {e}")
            return False

    def load_strategy_config(self, path: Path) -> Optional[Dict[str, Any]]:
        """
        Load strategy configuration from file.

        Args:
            path: Configuration file path

        Returns:
            Configuration dictionary or None
        """
        try:
            import yaml

            if not path.exists():
                logger.error(f"Configuration file not found: {path}")
                return None

            with open(path, 'r') as f:
                config = yaml.safe_load(f)

            logger.info(f"Strategy config loaded: {path}")
            return config

        except Exception as e:
            logger.error(f"Error loading strategy config: {e}")
            return None

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_strategy_documentation(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get strategy documentation.

        Args:
            name: Strategy name

        Returns:
            Documentation dict or None
        """
        registration = self._strategies.get(name)

        if not registration:
            return None

        return {
            "name": registration.name,
            "category": registration.category.value,
            "version": registration.version,
            "description": registration.description,
            "tags": registration.tags,
            "config_class": registration.config_class.__name__,
            "strategy_class": registration.strategy_class.__name__,
            "dependencies": registration.dependencies,
            "metadata": registration.metadata,
        }

    def get_all_documentation(self) -> Dict[str, Dict[str, Any]]:
        """
        Get documentation for all strategies.

        Returns:
            Dict of strategy name -> documentation
        """
        docs = {}

        for name in self._strategies:
            doc = self.get_strategy_documentation(name)
            if doc:
                docs[name] = doc

        return docs

    def get_strategy_class(self, name: str) -> Optional[Type[BaseStrategy]]:
        """
        Get strategy class.

        Args:
            name: Strategy name

        Returns:
            Strategy class or None
        """
        registration = self._strategies.get(name)
        return registration.strategy_class if registration else None

    def get_config_class(self, name: str) -> Optional[Type[StrategyConfig]]:
        """
        Get config class.

        Args:
            name: Strategy name

        Returns:
            Config class or None
        """
        registration = self._strategies.get(name)
        return registration.config_class if registration else None

    # ========================================================================
    # Dynamic Strategy Loading
    # ========================================================================

    def load_external_strategy(
        self,
        module_path: str,
        class_name: str,
        config_class_name: str,
        **kwargs,
    ) -> bool:
        """
        Load an external strategy from a module.

        Args:
            module_path: Module path
            class_name: Strategy class name
            config_class_name: Config class name
            **kwargs: Additional registration parameters

        Returns:
            True if loaded successfully
        """
        try:
            # Import module
            module = importlib.import_module(module_path)

            # Get strategy class
            strategy_class = getattr(module, class_name)

            # Get config class
            config_class = getattr(module, config_class_name)

            # Validate classes
            if not issubclass(strategy_class, BaseStrategy):
                logger.error(f"Strategy class must inherit from BaseStrategy")
                return False

            if not issubclass(config_class, StrategyConfig):
                logger.error(f"Config class must inherit from StrategyConfig")
                return False

            # Register strategy
            name = kwargs.get("name", class_name.lower())
            category = kwargs.get("category", StrategyCategory.CUSTOM)
            version = kwargs.get("version", "1.0.0")
            description = kwargs.get("description", f"External strategy: {name}")

            return self.register_strategy(
                name=name,
                category=category,
                strategy_class=strategy_class,
                config_class=config_class,
                version=version,
                description=description,
                tags=kwargs.get("tags", []),
                dependencies=kwargs.get("dependencies", []),
                is_active=kwargs.get("is_active", True),
                metadata=kwargs.get("metadata", {}),
            )

        except ImportError as e:
            logger.error(f"Error importing external strategy: {e}")
            return False

        except Exception as e:
            logger.error(f"Error loading external strategy: {e}")
            return False


# ============================================================================
# Singleton Access
# ============================================================================

def get_strategy_factory() -> StrategyFactory:
    """
    Get the global strategy factory instance.

    Returns:
        StrategyFactory instance
    """
    return StrategyFactory()


def create_strategy(
    name: str,
    config: Dict[str, Any],
    order_manager: OrderManager,
    risk_manager: RiskManager,
    market_data_provider: MarketDataProvider,
    **kwargs,
) -> Optional[BaseStrategy]:
    """
    Factory function to create a strategy.

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
    factory = get_strategy_factory()
    return factory.create_strategy(
        name=name,
        config=config,
        order_manager=order_manager,
        risk_manager=risk_manager,
        market_data_provider=market_data_provider,
        **kwargs,
    )


def list_strategies(category: Optional[StrategyCategory] = None) -> List[str]:
    """
    List available strategies.

    Args:
        category: Filter by category

    Returns:
        List of strategy names
    """
    factory = get_strategy_factory()
    return factory.get_strategy_names(category)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the strategy factory
    pass
