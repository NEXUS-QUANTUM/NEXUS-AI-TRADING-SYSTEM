# trading/bots/arbitrage_bot/strategies/__init__.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Complete Strategies Package

"""
Strategies Package - Complete Arbitrage Strategy Suite

This package provides a comprehensive suite of arbitrage strategies
for the NEXUS AI Trading System. It includes various strategy
implementations covering different arbitrage types and market conditions.

Architecture:
    - Base Classes: Abstract interfaces for all strategies
    - Strategy-Specific Implementations: Specialized strategies
    - Factory Pattern: Dynamic strategy instantiation
    - Adaptive Selection: Smart strategy selection
    - Performance Tracking: Strategy performance monitoring

Directory Structure:
    ├── __init__.py                  # Package initialization
    ├── adaptive_strategy.py         # Adaptive strategy
    ├── base_strategy.py             # Abstract base class
    ├── cross_chain_strategy.py      # Cross-chain arbitrage
    ├── cross_exchange_strategy.py   # Cross-exchange arbitrage
    ├── dex_strategy.py              # DEX arbitrage
    ├── flash_loan_strategy.py       # Flash loan arbitrage
    ├── futures_spot_strategy.py     # Futures-spot arbitrage
    ├── hybrid_strategy.py           # Hybrid strategy
    ├── mean_reversion_arbitrage.py  # Mean reversion arbitrage
    ├── mixed_strategy.py            # Mixed strategy
    ├── momentum_arbitrage.py        # Momentum arbitrage
    ├── statistical_strategy.py      # Statistical arbitrage
    ├── strategy_factory.py          # Factory pattern
    └── triangular_strategy.py       # Triangular arbitrage

Exports:
    - All strategy classes
    - Factory function for strategy creation
    - Base strategy classes
    - Utility functions and constants
"""

import asyncio
import logging
import threading
from typing import Dict, List, Optional, Type, Any, Union, Tuple, Set, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

# Import base strategy
try:
    from .base_strategy import (
        BaseStrategy,
        StrategyConfig,
        StrategyType,
        StrategyStatus,
        StrategyMetrics,
        StrategyResult,
        StrategyEvent,
        StrategyEventListener,
    )
except ImportError:
    class BaseStrategy:
        pass
    class StrategyConfig:
        pass
    class StrategyType(Enum):
        pass
    class StrategyStatus(Enum):
        pass
    class StrategyMetrics:
        pass
    class StrategyResult:
        pass
    class StrategyEvent:
        pass
    class StrategyEventListener:
        pass

# Import strategy implementations with error handling
try:
    from .adaptive_strategy import AdaptiveStrategy, AdaptiveConfig
except ImportError:
    class AdaptiveStrategy(BaseStrategy):
        pass
    class AdaptiveConfig:
        pass

try:
    from .cross_chain_strategy import CrossChainStrategy, CrossChainConfig
except ImportError:
    class CrossChainStrategy(BaseStrategy):
        pass
    class CrossChainConfig:
        pass

try:
    from .cross_exchange_strategy import CrossExchangeStrategy, CrossExchangeConfig
except ImportError:
    class CrossExchangeStrategy(BaseStrategy):
        pass
    class CrossExchangeConfig:
        pass

try:
    from .dex_strategy import DexStrategy, DexConfig
except ImportError:
    class DexStrategy(BaseStrategy):
        pass
    class DexConfig:
        pass

try:
    from .flash_loan_strategy import FlashLoanStrategy, FlashLoanConfig
except ImportError:
    class FlashLoanStrategy(BaseStrategy):
        pass
    class FlashLoanConfig:
        pass

try:
    from .futures_spot_strategy import FuturesSpotStrategy, FuturesSpotConfig
except ImportError:
    class FuturesSpotStrategy(BaseStrategy):
        pass
    class FuturesSpotConfig:
        pass

try:
    from .hybrid_strategy import HybridStrategy, HybridConfig
except ImportError:
    class HybridStrategy(BaseStrategy):
        pass
    class HybridConfig:
        pass

try:
    from .mean_reversion_arbitrage import MeanReversionStrategy, MeanReversionConfig
except ImportError:
    class MeanReversionStrategy(BaseStrategy):
        pass
    class MeanReversionConfig:
        pass

try:
    from .mixed_strategy import MixedStrategy, MixedConfig
except ImportError:
    class MixedStrategy(BaseStrategy):
        pass
    class MixedConfig:
        pass

try:
    from .momentum_arbitrage import MomentumArbitrage, MomentumArbitrageConfig
except ImportError:
    class MomentumArbitrage(BaseStrategy):
        pass
    class MomentumArbitrageConfig:
        pass

try:
    from .statistical_strategy import StatisticalStrategy, StatisticalConfig
except ImportError:
    class StatisticalStrategy(BaseStrategy):
        pass
    class StatisticalConfig:
        pass

try:
    from .triangular_strategy import TriangularStrategy, TriangularConfig
except ImportError:
    class TriangularStrategy(BaseStrategy):
        pass
    class TriangularConfig:
        pass

# Import factory
try:
    from .strategy_factory import (
        StrategyFactory,
        StrategyRegistry,
        StrategyType as FactoryStrategyType,
        StrategyMetadata,
        StrategyCreationParams,
        create_strategy,
        create_strategy_from_config,
        list_strategy_types,
        get_strategy,
        register_strategy_instance,
        remove_strategy_instance,
    )
except ImportError:
    class StrategyFactory:
        pass
    class StrategyRegistry:
        pass
    class FactoryStrategyType(Enum):
        pass
    class StrategyMetadata:
        pass
    class StrategyCreationParams:
        pass
    def create_strategy(*args, **kwargs):
        return None
    def create_strategy_from_config(*args, **kwargs):
        return None
    def list_strategy_types(*args, **kwargs):
        return []
    def get_strategy(*args, **kwargs):
        return None
    def register_strategy_instance(*args, **kwargs):
        pass
    def remove_strategy_instance(*args, **kwargs):
        return False

# Logger setup
logger = logging.getLogger(__name__)

# Version information
__version__ = "4.2.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Package metadata
PACKAGE_METADATA = {
    "name": "strategies",
    "version": __version__,
    "description": "Complete Arbitrage Strategy Suite",
    "author": __author__,
    "copyright": __copyright__,
    "strategies_count": 13,
    "supported_strategies": [
        "adaptive",
        "cross_chain",
        "cross_exchange",
        "dex",
        "flash_loan",
        "futures_spot",
        "hybrid",
        "mean_reversion",
        "mixed",
        "momentum",
        "statistical",
        "triangular",
    ],
    "supported_markets": [
        "spot",
        "futures",
        "perpetual",
        "option",
        "margin",
        "dex",
        "cross_chain",
    ],
    "supported_assets": [
        "crypto",
        "forex",
        "stocks",
        "commodities",
        "indices",
    ],
}

# Public API - All strategies
__all__ = [
    # Base classes
    'BaseStrategy',
    'StrategyConfig',
    'StrategyType',
    'StrategyStatus',
    'StrategyMetrics',
    'StrategyResult',
    'StrategyEvent',
    'StrategyEventListener',
    
    # Adaptive Strategy
    'AdaptiveStrategy',
    'AdaptiveConfig',
    
    # Cross-Chain Strategy
    'CrossChainStrategy',
    'CrossChainConfig',
    
    # Cross-Exchange Strategy
    'CrossExchangeStrategy',
    'CrossExchangeConfig',
    
    # DEX Strategy
    'DexStrategy',
    'DexConfig',
    
    # Flash Loan Strategy
    'FlashLoanStrategy',
    'FlashLoanConfig',
    
    # Futures-Spot Strategy
    'FuturesSpotStrategy',
    'FuturesSpotConfig',
    
    # Hybrid Strategy
    'HybridStrategy',
    'HybridConfig',
    
    # Mean Reversion Strategy
    'MeanReversionStrategy',
    'MeanReversionConfig',
    
    # Mixed Strategy
    'MixedStrategy',
    'MixedConfig',
    
    # Momentum Strategy
    'MomentumArbitrage',
    'MomentumArbitrageConfig',
    
    # Statistical Strategy
    'StatisticalStrategy',
    'StatisticalConfig',
    
    # Triangular Strategy
    'TriangularStrategy',
    'TriangularConfig',
    
    # Factory
    'StrategyFactory',
    'StrategyRegistry',
    'FactoryStrategyType',
    'StrategyMetadata',
    'StrategyCreationParams',
    'create_strategy',
    'create_strategy_from_config',
    'list_strategy_types',
    'get_strategy',
    'register_strategy_instance',
    'remove_strategy_instance',
    
    # Metadata
    'PACKAGE_METADATA',
    'get_version',
    'get_metadata',
    'list_strategies',
]


class StrategyEventType(Enum):
    """Strategy event types."""
    STARTED = "started"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESUMED = "resumed"
    OPPORTUNITY_FOUND = "opportunity_found"
    OPPORTUNITY_EXECUTED = "opportunity_executed"
    OPPORTUNITY_FAILED = "opportunity_failed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    METRICS_UPDATED = "metrics_updated"
    STRATEGY_CHANGED = "strategy_changed"
    RISK_LIMIT_REACHED = "risk_limit_reached"
    PERFORMANCE_UPDATE = "performance_update"


@dataclass
class StrategyEvent:
    """Strategy event."""
    event_type: StrategyEventType
    strategy_name: str
    strategy_type: StrategyType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None


class StrategyRegistry:
    """
    Registry for managing all strategy instances.
    
    This class provides centralized management of strategy instances,
    including creation, configuration, and lifecycle management.
    
    Features:
    - Singleton pattern for global access
    - Strategy registration and retrieval
    - Lifecycle management (start/stop)
    - Event system for strategy notifications
    - Metrics aggregation
    - Health monitoring
    """
    
    _instance = None
    _strategies: Dict[str, BaseStrategy] = {}
    _configs: Dict[str, StrategyConfig] = {}
    _listeners: List[Callable[[StrategyEvent], None]] = []
    _event_history: List[StrategyEvent] = []
    _max_event_history: int = 1000
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the registry."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.logger = logging.getLogger(f"{__name__}.Registry")
            self._lock = threading.Lock()
            self._strategy_metadata = {}
            self._register_strategy_metadata()
            self.logger.info("StrategyRegistry initialized")
    
    def _register_strategy_metadata(self) -> None:
        """Register metadata for all strategies."""
        self._strategy_metadata = {
            "adaptive": {
                "name": "Adaptive Strategy",
                "description": "Dynamically adapts to market conditions",
                "supported_markets": ["all"],
                "priority": 1,
                "is_experimental": False,
            },
            "cross_chain": {
                "name": "Cross-Chain Strategy",
                "description": "Arbitrage across different blockchain networks",
                "supported_markets": ["dex", "cross_chain"],
                "priority": 3,
                "is_experimental": True,
            },
            "cross_exchange": {
                "name": "Cross-Exchange Strategy",
                "description": "Arbitrage across different centralized exchanges",
                "supported_markets": ["spot", "futures"],
                "priority": 1,
                "is_experimental": False,
            },
            "dex": {
                "name": "DEX Strategy",
                "description": "Arbitrage on decentralized exchanges",
                "supported_markets": ["dex"],
                "priority": 1,
                "is_experimental": False,
            },
            "flash_loan": {
                "name": "Flash Loan Strategy",
                "description": "Capital-efficient arbitrage using flash loans",
                "supported_markets": ["dex"],
                "priority": 3,
                "is_experimental": True,
            },
            "futures_spot": {
                "name": "Futures-Spot Strategy",
                "description": "Basis trading between futures and spot markets",
                "supported_markets": ["spot", "futures"],
                "priority": 2,
                "is_experimental": False,
            },
            "hybrid": {
                "name": "Hybrid Strategy",
                "description": "Combines multiple strategies adaptively",
                "supported_markets": ["all"],
                "priority": 1,
                "is_experimental": False,
            },
            "mean_reversion": {
                "name": "Mean Reversion Strategy",
                "description": "Exploits price mean reversion",
                "supported_markets": ["spot"],
                "priority": 2,
                "is_experimental": False,
            },
            "mixed": {
                "name": "Mixed Strategy",
                "description": "Executes multiple strategies simultaneously",
                "supported_markets": ["all"],
                "priority": 2,
                "is_experimental": False,
            },
            "momentum": {
                "name": "Momentum Strategy",
                "description": "Leverages price momentum across markets",
                "supported_markets": ["spot", "futures"],
                "priority": 2,
                "is_experimental": False,
            },
            "statistical": {
                "name": "Statistical Strategy",
                "description": "Uses statistical methods for arbitrage",
                "supported_markets": ["spot"],
                "priority": 2,
                "is_experimental": False,
            },
            "triangular": {
                "name": "Triangular Strategy",
                "description": "Arbitrage across three trading pairs",
                "supported_markets": ["spot"],
                "priority": 2,
                "is_experimental": False,
            },
        }
    
    def register_strategy(
        self,
        name: str,
        strategy: BaseStrategy,
        config: Optional[StrategyConfig] = None
    ) -> None:
        """
        Register a strategy instance.
        
        Args:
            name: Strategy name
            strategy: Strategy instance
            config: Optional configuration
        """
        with self._lock:
            self._strategies[name] = strategy
            if config:
                self._configs[name] = config
            self._emit_event(StrategyEventType.STARTED, name, strategy.strategy_type)
            self.logger.info(f"Registered strategy: {name}")
    
    def unregister_strategy(self, name: str) -> None:
        """
        Unregister a strategy instance.
        
        Args:
            name: Strategy name
        """
        with self._lock:
            if name in self._strategies:
                try:
                    if hasattr(self._strategies[name], 'stop'):
                        self._strategies[name].stop()
                except Exception as e:
                    self.logger.error(f"Error stopping {name}: {e}")
                del self._strategies[name]
                if name in self._configs:
                    del self._configs[name]
                self._emit_event(StrategyEventType.STOPPED, name, None)
                self.logger.info(f"Unregistered strategy: {name}")
    
    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """
        Get a strategy by name.
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy instance or None
        """
        with self._lock:
            return self._strategies.get(name)
    
    def get_all_strategies(self) -> Dict[str, BaseStrategy]:
        """
        Get all registered strategies.
        
        Returns:
            Dictionary of strategy name to instance
        """
        with self._lock:
            return self._strategies.copy()
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a strategy.
        
        Args:
            name: Strategy name
            
        Returns:
            Metadata dictionary or None
        """
        return self._strategy_metadata.get(name)
    
    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for all strategies.
        
        Returns:
            Dictionary of strategy name to metadata
        """
        return self._strategy_metadata.copy()
    
    def start_all(self) -> Dict[str, bool]:
        """
        Start all registered strategies.
        
        Returns:
            Dictionary of strategy name to success status
        """
        results = {}
        for name, strategy in self._strategies.items():
            try:
                if hasattr(strategy, 'start'):
                    strategy.start()
                    results[name] = True
                    self._emit_event(StrategyEventType.STARTED, name, strategy.strategy_type)
                    self.logger.info(f"Started strategy: {name}")
                else:
                    results[name] = False
                    self.logger.warning(f"Strategy {name} has no start method")
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to start {name}: {e}")
                self._emit_event(StrategyEventType.ERROR, name, None, error=e)
        return results
    
    def stop_all(self) -> Dict[str, bool]:
        """
        Stop all registered strategies.
        
        Returns:
            Dictionary of strategy name to success status
        """
        results = {}
        for name, strategy in self._strategies.items():
            try:
                if hasattr(strategy, 'stop'):
                    strategy.stop()
                    results[name] = True
                    self._emit_event(StrategyEventType.STOPPED, name, strategy.strategy_type)
                    self.logger.info(f"Stopped strategy: {name}")
                else:
                    results[name] = False
                    self.logger.warning(f"Strategy {name} has no stop method")
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to stop {name}: {e}")
                self._emit_event(StrategyEventType.ERROR, name, None, error=e)
        return results
    
    def pause_all(self) -> Dict[str, bool]:
        """
        Pause all registered strategies.
        
        Returns:
            Dictionary of strategy name to success status
        """
        results = {}
        for name, strategy in self._strategies.items():
            try:
                if hasattr(strategy, 'pause'):
                    strategy.pause()
                    results[name] = True
                    self._emit_event(StrategyEventType.PAUSED, name, strategy.strategy_type)
                    self.logger.info(f"Paused strategy: {name}")
                else:
                    results[name] = False
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to pause {name}: {e}")
        return results
    
    def resume_all(self) -> Dict[str, bool]:
        """
        Resume all registered strategies.
        
        Returns:
            Dictionary of strategy name to success status
        """
        results = {}
        for name, strategy in self._strategies.items():
            try:
                if hasattr(strategy, 'resume'):
                    strategy.resume()
                    results[name] = True
                    self._emit_event(StrategyEventType.RESUMED, name, strategy.strategy_type)
                    self.logger.info(f"Resumed strategy: {name}")
                else:
                    results[name] = False
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to resume {name}: {e}")
        return results
    
    def add_listener(self, listener: Callable[[StrategyEvent], None]) -> None:
        """
        Add an event listener.
        
        Args:
            listener: Callback function for events
        """
        with self._lock:
            self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[StrategyEvent], None]) -> None:
        """
        Remove an event listener.
        
        Args:
            listener: Callback function to remove
        """
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
    
    def _emit_event(
        self,
        event_type: StrategyEventType,
        strategy_name: str,
        strategy_type: Optional[StrategyType],
        data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ) -> None:
        """
        Emit an event to all listeners.
        
        Args:
            event_type: Type of event
            strategy_name: Name of the strategy
            strategy_type: Type of the strategy
            data: Optional event data
            error: Optional error
        """
        event = StrategyEvent(
            event_type=event_type,
            strategy_name=strategy_name,
            strategy_type=strategy_type or StrategyType.MIXED,
            timestamp=datetime.utcnow(),
            data=data,
            error=error,
        )
        
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_event_history:
                self._event_history = self._event_history[-self._max_event_history:]
            
            for listener in self._listeners:
                try:
                    listener(event)
                except Exception as e:
                    self.logger.error(f"Listener error: {e}")
    
    def get_event_history(
        self,
        limit: int = 100,
        strategy_name: Optional[str] = None,
        event_type: Optional[StrategyEventType] = None
    ) -> List[StrategyEvent]:
        """
        Get event history.
        
        Args:
            limit: Maximum number of events
            strategy_name: Filter by strategy name
            event_type: Filter by event type
            
        Returns:
            List of events
        """
        with self._lock:
            events = self._event_history.copy()
        
        if strategy_name:
            events = [e for e in events if e.strategy_name == strategy_name]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics from all strategies.
        
        Returns:
            Aggregated metrics dictionary
        """
        aggregated = {
            "total_strategies": len(self._strategies),
            "active_strategies": 0,
            "total_opportunities": 0,
            "total_executions": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "total_errors": 0,
            "strategies": {},
        }
        
        for name, strategy in self._strategies.items():
            try:
                if hasattr(strategy, 'get_metrics'):
                    metrics = strategy.get_metrics()
                    if metrics:
                        aggregated["strategies"][name] = metrics
                        if metrics.get("is_running", False):
                            aggregated["active_strategies"] += 1
                        aggregated["total_opportunities"] += metrics.get("opportunities_detected", 0)
                        aggregated["total_executions"] += metrics.get("opportunities_executed", 0)
                        aggregated["total_profit"] += Decimal(str(metrics.get("total_profit", 0)))
                        aggregated["total_loss"] += Decimal(str(metrics.get("total_loss", 0)))
                        aggregated["net_profit"] += Decimal(str(metrics.get("net_profit", 0)))
                        aggregated["total_errors"] += metrics.get("errors", 0)
            except Exception as e:
                self.logger.error(f"Error getting metrics for {name}: {e}")
        
        return aggregated


# Global registry instance
strategy_registry = StrategyRegistry()


# Utility functions
def get_strategy(name: str) -> Optional[BaseStrategy]:
    """
    Get a strategy by name from the registry.
    
    Args:
        name: Strategy name
        
    Returns:
        Strategy instance or None
    """
    return strategy_registry.get_strategy(name)


def get_all_strategies() -> Dict[str, BaseStrategy]:
    """
    Get all strategies from the registry.
    
    Returns:
        Dictionary of strategy name to instance
    """
    return strategy_registry.get_all_strategies()


def create_strategy(
    strategy_type: Union[str, FactoryStrategyType],
    exchanges: Dict[ExchangeType, BaseExchange],
    executor: BaseExecutor,
    config: Optional[Dict[str, Any]] = None
) -> Optional[BaseStrategy]:
    """
    Create a strategy using the factory.
    
    Args:
        strategy_type: Type of strategy to create
        exchanges: Dictionary of exchange instances
        executor: Execution engine
        config: Optional configuration
        
    Returns:
        Strategy instance or None
    """
    from ..executors.base_executor import BaseExecutor as Executor
    return StrategyFactory.create_strategy_from_config(
        strategy_type, exchanges, executor, config or {}
    )


def list_strategies() -> List[str]:
    """
    List all available strategy types.
    
    Returns:
        List of strategy type names
    """
    return [s.value for s in list_strategy_types()]


def get_version() -> str:
    """Get package version."""
    return __version__


def get_metadata() -> Dict[str, Any]:
    """Get package metadata."""
    return PACKAGE_METADATA


def start_all_strategies() -> Dict[str, bool]:
    """
    Start all registered strategies.
    
    Returns:
        Dictionary of strategy name to success status
    """
    return strategy_registry.start_all()


def stop_all_strategies() -> Dict[str, bool]:
    """
    Stop all registered strategies.
    
    Returns:
        Dictionary of strategy name to success status
    """
    return strategy_registry.stop_all()


def pause_all_strategies() -> Dict[str, bool]:
    """
    Pause all registered strategies.
    
    Returns:
        Dictionary of strategy name to success status
    """
    return strategy_registry.pause_all()


def resume_all_strategies() -> Dict[str, bool]:
    """
    Resume all registered strategies.
    
    Returns:
        Dictionary of strategy name to success status
    """
    return strategy_registry.resume_all()


def get_aggregated_metrics() -> Dict[str, Any]:
    """
    Get aggregated metrics from all strategies.
    
    Returns:
        Aggregated metrics dictionary
    """
    return strategy_registry.get_aggregated_metrics()


def get_healthy_strategies() -> List[str]:
    """
    Get list of healthy strategies.
    
    Returns:
        List of strategy names
    """
    healthy = []
    for name, strategy in strategy_registry._strategies.items():
        try:
            if hasattr(strategy, 'get_metrics'):
                metrics = strategy.get_metrics()
                if metrics and metrics.get("is_running", False):
                    healthy.append(name)
        except Exception:
            pass
    return healthy


def add_strategy_listener(listener: Callable[[StrategyEvent], None]) -> None:
    """
    Add a strategy event listener.
    
    Args:
        listener: Callback function for events
    """
    strategy_registry.add_listener(listener)


def remove_strategy_listener(listener: Callable[[StrategyEvent], None]) -> None:
    """
    Remove a strategy event listener.
    
    Args:
        listener: Callback function to remove
    """
    strategy_registry.remove_listener(listener)


# Context manager for strategy lifecycle
@contextmanager
def strategy_context(
    strategy_type: Union[str, FactoryStrategyType],
    exchanges: Dict[ExchangeType, BaseExchange],
    executor: BaseExecutor,
    config: Optional[Dict[str, Any]] = None
):
    """
    Context manager for strategy lifecycle.
    
    Args:
        strategy_type: Type of strategy
        exchanges: Dictionary of exchange instances
        executor: Execution engine
        config: Optional configuration
        
    Yields:
        Strategy instance
    """
    strategy = create_strategy(strategy_type, exchanges, executor, config)
    if not strategy:
        raise ValueError(f"Failed to create strategy: {strategy_type}")
    
    try:
        if hasattr(strategy, 'start'):
            strategy.start()
        yield strategy
    finally:
        if hasattr(strategy, 'stop'):
            strategy.stop()


# Package initialization
logger.info(f"Initializing Strategies Package v{__version__}")
logger.info(f"Registered {len(strategy_registry.get_all_metadata())} strategy types")
logger.info(f"Package metadata: {PACKAGE_METADATA}")

# Auto-register available strategies
try:
    for strategy_type in ['momentum', 'statistical', 'triangular']:
        try:
            strategy = create_strategy(strategy_type, {}, None)
            if strategy:
                strategy_registry.register_strategy(strategy_type, strategy)
        except Exception as e:
            logger.debug(f"Failed to auto-register {strategy_type}: {e}")
except Exception as e:
    logger.debug(f"Auto-registration failed: {e}")


# Lazy imports for circular dependency resolution
def __getattr__(name: str) -> Any:
    """
    Lazy import for submodules.
    
    This allows for clean imports while avoiding circular dependencies.
    """
    if name in ['adaptive_strategy', 'cross_chain_strategy', 'cross_exchange_strategy',
                'dex_strategy', 'flash_loan_strategy', 'futures_spot_strategy',
                'hybrid_strategy', 'mean_reversion_arbitrage', 'mixed_strategy',
                'momentum_arbitrage', 'statistical_strategy', 'strategy_factory',
                'triangular_strategy', 'base_strategy']:
        raise AttributeError(f"Module {name} not loaded. Please import directly.")
    raise AttributeError(f"module {__name__} has no attribute {name}")


# Import contextlib for context manager
import contextlib
from contextlib import contextmanager
