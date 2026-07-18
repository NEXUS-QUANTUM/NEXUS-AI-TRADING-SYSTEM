# trading/strategies/factory.py
"""
NEXUS AI TRADING SYSTEM - Strategy Factory
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides a factory pattern implementation for creating
trading strategy instances. It supports dynamic registration and
instantiation of strategies based on configuration.

The factory enables:
- Centralized strategy creation
- Dynamic strategy registration
- Configuration-based instantiation
- Strategy discovery and loading
- Dependency injection for strategies
"""

import importlib
import importlib.util
import inspect
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union, Callable, Awaitable
from enum import Enum

from shared.utilities.logger import get_logger
from .base import BaseStrategy, StrategyConfig, StrategyType

logger = get_logger(__name__)


# ============================================================================
# STRATEGY REGISTRY
# ============================================================================

@dataclass
class StrategyMetadata:
    """Metadata for a registered strategy"""
    name: str
    strategy_type: StrategyType
    strategy_class: Type[BaseStrategy]
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    is_builtin: bool = False
    is_enabled: bool = True
    priority: int = 0


class StrategyRegistry:
    """
    Registry for strategy implementations.
    
    Manages the registration, discovery, and retrieval of strategy classes.
    Supports dynamic loading of strategy modules.
    """
    
    def __init__(self):
        """Initialize the strategy registry."""
        self._strategies: Dict[str, StrategyMetadata] = {}
        self._strategy_types: Dict[StrategyType, List[str]] = {}
        self._aliases: Dict[str, str] = {}  # alias -> strategy_name
        self._initialized = False
        self.logger = logger
        
        # Register built-in strategies
        self._register_builtin_strategies()
    
    def _register_builtin_strategies(self) -> None:
        """Register built-in strategy implementations."""
        from .ai_ensemble import AIEnsembleStrategy
        from .arbitrage import ArbitrageStrategy
        from .breakout import BreakoutStrategy
        from .custom import CustomStrategy
        from .grid_trading import GridTradingStrategy
        from .martingale import MartingaleStrategy
        from .mean_reversion import MeanReversionStrategy
        from .momentum import MomentumStrategy
        from .pairs_trading import PairsTradingStrategy
        from .scalping import ScalpingStrategy
        
        builtin_strategies = [
            ("ai_ensemble", StrategyType.AI_ENSEMBLE, AIEnsembleStrategy, "AI Ensemble Trading Strategy"),
            ("arbitrage", StrategyType.ARBITRAGE, ArbitrageStrategy, "Arbitrage Trading Strategy"),
            ("breakout", StrategyType.BREAKOUT, BreakoutStrategy, "Breakout Trading Strategy"),
            ("custom", StrategyType.CUSTOM, CustomStrategy, "Custom Trading Strategy"),
            ("grid_trading", StrategyType.GRID, GridTradingStrategy, "Grid Trading Strategy"),
            ("martingale", StrategyType.CUSTOM, MartingaleStrategy, "Martingale Trading Strategy"),
            ("mean_reversion", StrategyType.MEAN_REVERSION, MeanReversionStrategy, "Mean Reversion Strategy"),
            ("momentum", StrategyType.MOMENTUM, MomentumStrategy, "Momentum Trading Strategy"),
            ("pairs_trading", StrategyType.CUSTOM, PairsTradingStrategy, "Pairs Trading Strategy"),
            ("scalping", StrategyType.SCALPING, ScalpingStrategy, "Scalping Trading Strategy"),
        ]
        
        for name, strategy_type, strategy_class, description in builtin_strategies:
            self.register(
                name=name,
                strategy_type=strategy_type,
                strategy_class=strategy_class,
                description=description,
                is_builtin=True,
            )
        
        self.logger.info(f"Registered {len(builtin_strategies)} built-in strategies")
    
    def register(
        self,
        name: str,
        strategy_type: StrategyType,
        strategy_class: Type[BaseStrategy],
        description: str = "",
        version: str = "1.0.0",
        author: str = "",
        tags: Optional[List[str]] = None,
        config_schema: Optional[Dict[str, Any]] = None,
        is_builtin: bool = False,
        is_enabled: bool = True,
        priority: int = 0,
        aliases: Optional[List[str]] = None,
    ) -> None:
        """
        Register a strategy implementation.
        
        Args:
            name: Strategy name
            strategy_type: Type of strategy
            strategy_class: Strategy class
            description: Strategy description
            version: Strategy version
            author: Strategy author
            tags: Strategy tags
            config_schema: Configuration schema
            is_builtin: Whether strategy is built-in
            is_enabled: Whether strategy is enabled
            priority: Strategy priority
            aliases: Optional aliases for the strategy
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(
                f"Strategy class {strategy_class.__name__} must inherit from BaseStrategy"
            )
        
        metadata = StrategyMetadata(
            name=name,
            strategy_type=strategy_type,
            strategy_class=strategy_class,
            description=description,
            version=version,
            author=author,
            tags=tags or [],
            config_schema=config_schema,
            is_builtin=is_builtin,
            is_enabled=is_enabled,
            priority=priority,
        )
        
        self._strategies[name] = metadata
        
        # Add to type mapping
        if strategy_type not in self._strategy_types:
            self._strategy_types[strategy_type] = []
        if name not in self._strategy_types[strategy_type]:
            self._strategy_types[strategy_type].append(name)
        
        # Add aliases
        if aliases:
            for alias in aliases:
                self._aliases[alias] = name
        
        self.logger.info(f"Registered strategy: {name} ({strategy_type.value})")
    
    def get(self, name: str) -> Optional[StrategyMetadata]:
        """
        Get strategy metadata by name.
        
        Args:
            name: Strategy name or alias
            
        Returns:
            Optional[StrategyMetadata]: Strategy metadata or None
        """
        # Check alias
        if name in self._aliases:
            name = self._aliases[name]
        
        return self._strategies.get(name)
    
    def get_class(self, name: str) -> Optional[Type[BaseStrategy]]:
        """
        Get strategy class by name.
        
        Args:
            name: Strategy name or alias
            
        Returns:
            Optional[Type[BaseStrategy]]: Strategy class or None
        """
        metadata = self.get(name)
        return metadata.strategy_class if metadata else None
    
    def get_by_type(self, strategy_type: StrategyType) -> List[StrategyMetadata]:
        """
        Get all strategies of a specific type.
        
        Args:
            strategy_type: Strategy type
            
        Returns:
            List[StrategyMetadata]: List of strategy metadata
        """
        names = self._strategy_types.get(strategy_type, [])
        return [self._strategies[name] for name in names if name in self._strategies]
    
    def list_strategies(self) -> List[str]:
        """
        List all registered strategies.
        
        Returns:
            List[str]: List of strategy names
        """
        return list(self._strategies.keys())
    
    def get_all_metadata(self) -> Dict[str, StrategyMetadata]:
        """
        Get all strategy metadata.
        
        Returns:
            Dict[str, StrategyMetadata]: Strategy metadata by name
        """
        return dict(self._strategies)
    
    def is_registered(self, name: str) -> bool:
        """
        Check if a strategy is registered.
        
        Args:
            name: Strategy name or alias
            
        Returns:
            bool: True if strategy is registered
        """
        if name in self._aliases:
            name = self._aliases[name]
        return name in self._strategies
    
    def enable(self, name: str) -> bool:
        """
        Enable a strategy.
        
        Args:
            name: Strategy name or alias
            
        Returns:
            bool: True if strategy was enabled
        """
        metadata = self.get(name)
        if metadata:
            metadata.is_enabled = True
            self.logger.info(f"Enabled strategy: {name}")
            return True
        return False
    
    def disable(self, name: str) -> bool:
        """
        Disable a strategy.
        
        Args:
            name: Strategy name or alias
            
        Returns:
            bool: True if strategy was disabled
        """
        metadata = self.get(name)
        if metadata:
            metadata.is_enabled = False
            self.logger.info(f"Disabled strategy: {name}")
            return True
        return False
    
    def discover_strategies(self, directory: Optional[Path] = None) -> int:
        """
        Discover and register strategies from a directory.
        
        Args:
            directory: Directory to scan
            
        Returns:
            int: Number of strategies discovered
        """
        if directory is None:
            directory = Path(__file__).parent
        
        discovered = 0
        
        # Files to skip
        skip_files = [
            "__init__.py",
            "base.py",
            "factory.py",
        ]
        
        for file_path in directory.glob("*.py"):
            if file_path.name in skip_files:
                continue
            
            if file_path.name.startswith("__"):
                continue
            
            try:
                module_name = file_path.stem
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    continue
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Look for strategy classes in the module
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, BaseStrategy)
                        and obj.__module__ == module_name
                        and obj not in [BaseStrategy]
                    ):
                        # Determine strategy name from class name or module
                        strategy_name = self._infer_strategy_name(obj, module_name)
                        strategy_type = self._infer_strategy_type(obj)
                        
                        # Check if already registered
                        if self.is_registered(strategy_name):
                            continue
                        
                        self.register(
                            name=strategy_name,
                            strategy_type=strategy_type,
                            strategy_class=obj,
                            description=f"Discovered strategy: {strategy_name}",
                            is_builtin=False,
                        )
                        discovered += 1
                        
            except Exception as e:
                self.logger.warning(f"Failed to discover strategy in {file_path.name}: {e}")
        
        return discovered
    
    def _infer_strategy_name(self, strategy_class: Type[BaseStrategy], module_name: str) -> str:
        """
        Infer strategy name from class.
        
        Args:
            strategy_class: Strategy class
            module_name: Module name
            
        Returns:
            str: Strategy name
        """
        # Use class name
        class_name = strategy_class.__name__.lower()
        
        # Remove common suffixes
        for suffix in ["strategy", "strategie", "strategy"]:
            if class_name.endswith(suffix):
                class_name = class_name[:-len(suffix)]
        
        if class_name:
            return class_name
        
        return module_name
    
    def _infer_strategy_type(self, strategy_class: Type[BaseStrategy]) -> StrategyType:
        """
        Infer strategy type from class.
        
        Args:
            strategy_class: Strategy class
            
        Returns:
            StrategyType: Inferred strategy type
        """
        class_name = strategy_class.__name__.lower()
        
        # Map class names to strategy types
        type_mapping = {
            "trend": StrategyType.TREND_FOLLOWING,
            "trendfollowing": StrategyType.TREND_FOLLOWING,
            "meanreversion": StrategyType.MEAN_REVERSION,
            "reversion": StrategyType.MEAN_REVERSION,
            "breakout": StrategyType.BREAKOUT,
            "arbitrage": StrategyType.ARBITRAGE,
            "scalping": StrategyType.SCALPING,
            "momentum": StrategyType.MOMENTUM,
            "grid": StrategyType.GRID,
            "ai": StrategyType.AI_ENSEMBLE,
            "aiensemble": StrategyType.AI_ENSEMBLE,
            "machinelearning": StrategyType.MACHINE_LEARNING,
            "deeplearning": StrategyType.DEEP_LEARNING,
            "reinforcement": StrategyType.REINFORCEMENT,
            "sentiment": StrategyType.SENTIMENT,
        }
        
        for pattern, strategy_type in type_mapping.items():
            if pattern in class_name:
                return strategy_type
        
        return StrategyType.CUSTOM
    
    def clear(self) -> None:
        """Clear all registered strategies (except built-in)."""
        self._strategies = {
            name: meta for name, meta in self._strategies.items()
            if meta.is_builtin
        }
        self._strategy_types = {}
        self._aliases = {}
        
        # Rebuild type index
        for meta in self._strategies.values():
            if meta.strategy_type not in self._strategy_types:
                self._strategy_types[meta.strategy_type] = []
            self._strategy_types[meta.strategy_type].append(meta.name)
        
        self.logger.info("Cleared strategy registry (kept built-in strategies)")


# ============================================================================
# STRATEGY INSTANCE CACHE
# ============================================================================

class StrategyCache:
    """
    Cache for strategy instances.
    
    Manages strategy instance lifecycle including creation, caching,
    reuse, and cleanup of strategy instances.
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize the strategy cache.
        
        Args:
            max_size: Maximum number of cached instances
        """
        self._cache: Dict[str, BaseStrategy] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self.logger = logger
    
    async def get_or_create(
        self,
        key: str,
        factory: Callable[[], Awaitable[BaseStrategy]],
    ) -> BaseStrategy:
        """
        Get a cached strategy or create a new one.
        
        Args:
            key: Cache key
            factory: Async factory function
            
        Returns:
            BaseStrategy: Strategy instance
        """
        async with self._lock:
            if key in self._cache:
                return self._cache[key]
            
            strategy = await factory()
            
            if len(self._cache) >= self._max_size:
                await self._evict_oldest()
            
            self._cache[key] = strategy
            return strategy
    
    async def _evict_oldest(self) -> None:
        """Evict the oldest cached strategy."""
        if not self._cache:
            return
        
        # Find oldest by creation time (simplified)
        oldest_key = next(iter(self._cache))
        await self._close_strategy(oldest_key)
    
    async def _close_strategy(self, key: str) -> None:
        """Close a cached strategy."""
        if key in self._cache:
            try:
                strategy = self._cache[key]
                await strategy.on_stop()
                await strategy.cleanup()
            except Exception as e:
                self.logger.error(f"Error closing cached strategy {key}: {e}")
            finally:
                del self._cache[key]
    
    async def clear(self) -> None:
        """Clear all cached strategies."""
        for key in list(self._cache.keys()):
            await self._close_strategy(key)
        self.logger.info("Cleared strategy cache")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict: Cache statistics
        """
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "strategies": list(self._cache.keys()),
        }


# ============================================================================
# STRATEGY FACTORY
# ============================================================================

class StrategyFactory:
    """
    Factory for creating strategy instances.
    
    Provides centralized strategy creation with:
    - Automatic strategy registration and discovery
    - Instance caching for performance
    - Configuration-based instantiation
    - Dependency injection
    """
    
    _registry: Optional[StrategyRegistry] = None
    _cache: Optional[StrategyCache] = None
    _initialized = False
    
    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure the factory is initialized."""
        if cls._initialized:
            return
        
        cls._registry = StrategyRegistry()
        cls._cache = StrategyCache()
        cls._initialized = True
        
        logger.info("StrategyFactory initialized")
    
    @classmethod
    def initialize(cls, auto_discover: bool = True) -> None:
        """
        Initialize the strategy factory.
        
        Args:
            auto_discover: Whether to auto-discover strategy implementations
        """
        if cls._initialized:
            return
        
        cls._registry = StrategyRegistry()
        cls._cache = StrategyCache()
        
        if auto_discover:
            # Discover strategies in the strategies directory
            strategies_dir = Path(__file__).parent
            discovered = cls._registry.discover_strategies(strategies_dir)
            logger.info(f"Discovered {discovered} strategy implementations")
        
        cls._initialized = True
        logger.info("StrategyFactory initialized")
    
    @classmethod
    def register_strategy(
        cls,
        name: str,
        strategy_type: StrategyType,
        strategy_class: Type[BaseStrategy],
        description: str = "",
        **kwargs,
    ) -> None:
        """
        Register a strategy implementation.
        
        Args:
            name: Strategy name
            strategy_type: Strategy type
            strategy_class: Strategy class
            description: Strategy description
            **kwargs: Additional metadata
        """
        cls._ensure_initialized()
        cls._registry.register(name, strategy_type, strategy_class, description, **kwargs)
    
    @classmethod
    def get_strategy_class(cls, name: str) -> Optional[Type[BaseStrategy]]:
        """
        Get a strategy class by name.
        
        Args:
            name: Strategy name or alias
            
        Returns:
            Optional[Type[BaseStrategy]]: Strategy class or None
        """
        cls._ensure_initialized()
        return cls._registry.get_class(name)
    
    @classmethod
    def get_strategy_metadata(cls, name: str) -> Optional[StrategyMetadata]:
        """
        Get strategy metadata by name.
        
        Args:
            name: Strategy name or alias
            
        Returns:
            Optional[StrategyMetadata]: Strategy metadata or None
        """
        cls._ensure_initialized()
        return cls._registry.get(name)
    
    @classmethod
    def create_strategy(
        cls,
        name: str,
        config: StrategyConfig,
        extra_params: Optional[Dict[str, Any]] = None,
        use_cache: bool = False,
    ) -> BaseStrategy:
        """
        Create a strategy instance (synchronous).
        
        Args:
            name: Strategy name or alias
            config: Strategy configuration
            extra_params: Additional parameters for strategy
            use_cache: Whether to use cache
            
        Returns:
            BaseStrategy: Strategy instance
            
        Raises:
            ValueError: If strategy not found
        """
        cls._ensure_initialized()
        
        metadata = cls._registry.get(name)
        if not metadata:
            raise ValueError(
                f"Strategy '{name}' not registered. "
                f"Available: {cls._registry.list_strategies()}"
            )
        
        if not metadata.is_enabled:
            raise ValueError(f"Strategy '{name}' is disabled")
        
        strategy_class = metadata.strategy_class
        
        try:
            # Create strategy instance
            if extra_params:
                strategy = strategy_class(config, **extra_params)
            else:
                strategy = strategy_class(config)
            
            return strategy
            
        except Exception as e:
            raise RuntimeError(f"Failed to create strategy '{name}': {e}")
    
    @classmethod
    async def create_strategy_async(
        cls,
        name: str,
        config: StrategyConfig,
        extra_params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> BaseStrategy:
        """
        Create a strategy instance (asynchronous).
        
        Args:
            name: Strategy name or alias
            config: Strategy configuration
            extra_params: Additional parameters for strategy
            use_cache: Whether to use cache
            
        Returns:
            BaseStrategy: Strategy instance
        """
        cls._ensure_initialized()
        
        metadata = cls._registry.get(name)
        if not metadata:
            raise ValueError(
                f"Strategy '{name}' not registered. "
                f"Available: {cls._registry.list_strategies()}"
            )
        
        if not metadata.is_enabled:
            raise ValueError(f"Strategy '{name}' is disabled")
        
        # Generate cache key
        cache_key = f"{name}:{config.symbol or 'all'}:{config.timeframe}"
        
        if use_cache:
            async def create() -> BaseStrategy:
                if extra_params:
                    return metadata.strategy_class(config, **extra_params)
                return metadata.strategy_class(config)
            
            return await cls._cache.get_or_create(cache_key, create)
        
        # Create directly
        try:
            if extra_params:
                return metadata.strategy_class(config, **extra_params)
            return metadata.strategy_class(config)
        except Exception as e:
            raise RuntimeError(f"Failed to create strategy '{name}': {e}")
    
    @classmethod
    def create_from_dict(
        cls,
        config_dict: Dict[str, Any],
        use_cache: bool = False,
    ) -> BaseStrategy:
        """
        Create a strategy from a dictionary configuration.
        
        Args:
            config_dict: Configuration dictionary
            use_cache: Whether to use cache
            
        Returns:
            BaseStrategy: Strategy instance
        """
        # Extract strategy name
        name = config_dict.get("name", "custom")
        
        # Build StrategyConfig
        strategy_config = StrategyConfig(
            name=name,
            strategy_type=StrategyType(config_dict.get("strategy_type", "custom")),
            symbol=config_dict.get("symbol"),
            timeframe=config_dict.get("timeframe", "1h"),
            max_positions=config_dict.get("max_positions", 1),
            position_size=config_dict.get("position_size", 1000.0),
            max_position_size=config_dict.get("max_position_size", 100000.0),
            min_position_size=config_dict.get("min_position_size", 10.0),
            risk_per_trade=config_dict.get("risk_per_trade", 0.01),
            stop_loss_pct=config_dict.get("stop_loss_pct", 0.02),
            take_profit_pct=config_dict.get("take_profit_pct", 0.04),
            trailing_stop_pct=config_dict.get("trailing_stop_pct", 0.0),
            max_drawdown=config_dict.get("max_drawdown", 0.10),
            min_confidence=config_dict.get("min_confidence", 0.5),
            cooldown=config_dict.get("cooldown", 0),
            backtest_mode=config_dict.get("backtest_mode", False),
            params=config_dict.get("params", {}),
        )
        
        # Extract extra parameters
        extra_params = {}
        for key in ["custom_config", "breakout_config", "arbitrage_config", "ensemble_config"]:
            if key in config_dict:
                extra_params[key] = config_dict[key]
        
        return cls.create_strategy(name, strategy_config, extra_params, use_cache)
    
    @classmethod
    async def create_from_dict_async(
        cls,
        config_dict: Dict[str, Any],
        use_cache: bool = True,
    ) -> BaseStrategy:
        """
        Create a strategy from a dictionary configuration (async).
        
        Args:
            config_dict: Configuration dictionary
            use_cache: Whether to use cache
            
        Returns:
            BaseStrategy: Strategy instance
        """
        # Extract strategy name
        name = config_dict.get("name", "custom")
        
        # Build StrategyConfig
        strategy_config = StrategyConfig(
            name=name,
            strategy_type=StrategyType(config_dict.get("strategy_type", "custom")),
            symbol=config_dict.get("symbol"),
            timeframe=config_dict.get("timeframe", "1h"),
            max_positions=config_dict.get("max_positions", 1),
            position_size=config_dict.get("position_size", 1000.0),
            max_position_size=config_dict.get("max_position_size", 100000.0),
            min_position_size=config_dict.get("min_position_size", 10.0),
            risk_per_trade=config_dict.get("risk_per_trade", 0.01),
            stop_loss_pct=config_dict.get("stop_loss_pct", 0.02),
            take_profit_pct=config_dict.get("take_profit_pct", 0.04),
            trailing_stop_pct=config_dict.get("trailing_stop_pct", 0.0),
            max_drawdown=config_dict.get("max_drawdown", 0.10),
            min_confidence=config_dict.get("min_confidence", 0.5),
            cooldown=config_dict.get("cooldown", 0),
            backtest_mode=config_dict.get("backtest_mode", False),
            params=config_dict.get("params", {}),
        )
        
        # Extract extra parameters
        extra_params = {}
        for key in ["custom_config", "breakout_config", "arbitrage_config", "ensemble_config"]:
            if key in config_dict:
                extra_params[key] = config_dict[key]
        
        return await cls.create_strategy_async(name, strategy_config, extra_params, use_cache)
    
    @classmethod
    def get_registry(cls) -> StrategyRegistry:
        """
        Get the strategy registry.
        
        Returns:
            StrategyRegistry: Strategy registry
        """
        cls._ensure_initialized()
        return cls._registry
    
    @classmethod
    def get_cache(cls) -> StrategyCache:
        """
        Get the strategy cache.
        
        Returns:
            StrategyCache: Strategy cache
        """
        cls._ensure_initialized()
        return cls._cache
    
    @classmethod
    async def clear_cache(cls) -> None:
        """Clear the strategy cache."""
        cls._ensure_initialized()
        await cls._cache.clear()
    
    @classmethod
    def list_available_strategies(cls) -> List[Dict[str, Any]]:
        """
        List all available strategies with metadata.
        
        Returns:
            List[Dict[str, Any]]: List of strategy information
        """
        cls._ensure_initialized()
        
        strategies = []
        for name, metadata in cls._registry.get_all_metadata().items():
            strategies.append({
                "name": name,
                "type": metadata.strategy_type.value,
                "description": metadata.description,
                "version": metadata.version,
                "author": metadata.author,
                "tags": metadata.tags,
                "is_builtin": metadata.is_builtin,
                "is_enabled": metadata.is_enabled,
                "priority": metadata.priority,
            })
        
        return sorted(strategies, key=lambda x: (-x["priority"], x["name"]))
    
    @classmethod
    async def close_all(cls) -> None:
        """Close all strategy instances and clean up."""
        if cls._cache:
            await cls._cache.clear()
        
        cls._initialized = False
        logger.info("StrategyFactory closed")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_strategy(
    name: str,
    config: StrategyConfig,
    **kwargs,
) -> BaseStrategy:
    """
    Create a strategy instance (convenience function).
    
    Args:
        name: Strategy name
        config: Strategy configuration
        **kwargs: Additional parameters
        
    Returns:
        BaseStrategy: Strategy instance
    """
    return StrategyFactory.create_strategy(name, config, kwargs)


async def create_strategy_async(
    name: str,
    config: StrategyConfig,
    **kwargs,
) -> BaseStrategy:
    """
    Create a strategy instance (async convenience function).
    
    Args:
        name: Strategy name
        config: Strategy configuration
        **kwargs: Additional parameters
        
    Returns:
        BaseStrategy: Strategy instance
    """
    return await StrategyFactory.create_strategy_async(name, config, kwargs)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Registry
    "StrategyRegistry",
    "StrategyMetadata",
    
    # Cache
    "StrategyCache",
    
    # Factory
    "StrategyFactory",
    
    # Convenience functions
    "create_strategy",
    "create_strategy_async",
]
