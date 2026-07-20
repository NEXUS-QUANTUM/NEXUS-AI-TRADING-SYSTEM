# trading/bots/arbitrage_bot/executors/__init__.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Complete Executors Package

"""
Executors Package - Complete Execution Engine Suite

This package provides a comprehensive suite of execution engines
for the NEXUS AI Trading System. It includes various execution
strategies for arbitrage opportunities across different markets.

Architecture:
    - Base Classes: Abstract interfaces for all executors
    - Strategy-Specific Executors: Specialized implementations
    - Factory Pattern: Dynamic executor instantiation
    - Smart Selection: Automatic strategy selection
    - Performance Tracking: Execution monitoring and optimization

Directory Structure:
    ├── __init__.py                  # Package initialization
    ├── base_executor.py             # Abstract base class
    ├── batch_executor.py            # Batch execution
    ├── cross_chain_executor.py      # Cross-chain arbitrage
    ├── cross_exchange_executor.py   # Cross-exchange arbitrage
    ├── dex_executor.py              # DEX execution
    ├── executor_factory.py          # Factory pattern
    ├── flash_loan_executor.py       # Flash loan execution
    ├── futures_spot_executor.py     # Basis trading
    ├── mixed_executor.py            # Mixed strategy execution
    ├── order_executor.py            # Order execution
    ├── parallel_executor.py         # Parallel execution
    ├── sequential_executor.py       # Sequential execution
    ├── smart_executor.py            # Smart strategy selection
    ├── statistical_executor.py      # Statistical arbitrage
    └── triangular_executor.py       # Triangular arbitrage

Exports:
    - All executor classes
    - Factory function for executor creation
    - Base executor classes
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

# Import base executor
from .base_executor import (
    BaseExecutor,
    ExecutionType,
    ExecutionStatus,
    ExecutionPriority,
    ExecutionRisk,
    ExecutionConfig,
    ExecutionOrder,
    ExecutionPosition,
    ExecutionResult,
    ExecutionPlan,
    ExecutionListener,
)

# Import executor implementations with error handling
try:
    from .batch_executor import BatchExecutor, BatchConfig, BatchOrder, BatchResult
except ImportError:
    class BatchExecutor(BaseExecutor):
        pass
    class BatchConfig:
        pass
    class BatchOrder:
        pass
    class BatchResult:
        pass

try:
    from .cross_exchange_executor import (
        CrossExchangeExecutor,
        CrossExchangeConfig,
        CrossExchangeOrder,
        CrossExchangePosition,
    )
except ImportError:
    class CrossExchangeExecutor(BaseExecutor):
        pass
    class CrossExchangeConfig:
        pass
    class CrossExchangeOrder:
        pass
    class CrossExchangePosition:
        pass

try:
    from .cross_chain_executor import (
        CrossChainExecutor,
        CrossChainConfig,
        BridgeProtocol,
        BlockchainChain,
        BridgeTransaction,
        CrossChainOrder,
        CrossChainPosition,
    )
except ImportError:
    class CrossChainExecutor(BaseExecutor):
        pass
    class CrossChainConfig:
        pass
    class BridgeProtocol(Enum):
        pass
    class BlockchainChain(Enum):
        pass
    class BridgeTransaction:
        pass
    class CrossChainOrder:
        pass
    class CrossChainPosition:
        pass

try:
    from .dex_executor import DEXExecutor, DEXConfig, DEXRoute, DEXPosition
except ImportError:
    class DEXExecutor(BaseExecutor):
        pass
    class DEXConfig:
        pass
    class DEXRoute:
        pass
    class DEXPosition:
        pass

try:
    from .flash_loan_executor import (
        FlashLoanExecutor,
        FlashLoanConfig,
        FlashLoanProtocol,
        FlashLoanInfo,
        FlashLoanExecution,
        FlashLoanPosition,
    )
except ImportError:
    class FlashLoanExecutor(BaseExecutor):
        pass
    class FlashLoanConfig:
        pass
    class FlashLoanProtocol(Enum):
        pass
    class FlashLoanInfo:
        pass
    class FlashLoanExecution:
        pass
    class FlashLoanPosition:
        pass

try:
    from .futures_spot_executor import (
        FuturesSpotExecutor,
        FuturesSpotConfig,
        BasisData,
        FuturesSpotPosition,
    )
except ImportError:
    class FuturesSpotExecutor(BaseExecutor):
        pass
    class FuturesSpotConfig:
        pass
    class BasisData:
        pass
    class FuturesSpotPosition:
        pass

try:
    from .mixed_executor import MixedExecutor, MixedConfig, StrategyExecution, MixedPosition
except ImportError:
    class MixedExecutor(BaseExecutor):
        pass
    class MixedConfig:
        pass
    class StrategyExecution:
        pass
    class MixedPosition:
        pass

try:
    from .order_executor import OrderExecutor, OrderConfig, OrderExecution, OrderRoute, OrderResult
except ImportError:
    class OrderExecutor(BaseExecutor):
        pass
    class OrderConfig:
        pass
    class OrderExecution:
        pass
    class OrderRoute:
        pass
    class OrderResult:
        pass

try:
    from .parallel_executor import ParallelExecutor, ParallelConfig, ParallelTask, ParallelResult
except ImportError:
    class ParallelExecutor(BaseExecutor):
        pass
    class ParallelConfig:
        pass
    class ParallelTask:
        pass
    class ParallelResult:
        pass

try:
    from .sequential_executor import SequentialExecutor, SequentialConfig, Step, SequentialResult
except ImportError:
    class SequentialExecutor(BaseExecutor):
        pass
    class SequentialConfig:
        pass
    class Step:
        pass
    class SequentialResult:
        pass

try:
    from .smart_executor import (
        SmartExecutor,
        SmartConfig,
        ExecutionStrategy,
        StrategyScore,
        MarketCondition,
        StrategyRecommendation,
    )
except ImportError:
    class SmartExecutor(BaseExecutor):
        pass
    class SmartConfig:
        pass
    class ExecutionStrategy(Enum):
        pass
    class StrategyScore:
        pass
    class MarketCondition:
        pass
    class StrategyRecommendation:
        pass

try:
    from .statistical_executor import (
        StatisticalExecutor,
        StatisticalConfig,
        StatisticalPair,
        StatisticalPosition,
    )
except ImportError:
    class StatisticalExecutor(BaseExecutor):
        pass
    class StatisticalConfig:
        pass
    class StatisticalPair:
        pass
    class StatisticalPosition:
        pass

try:
    from .triangular_executor import (
        TriangularExecutor,
        TriangularConfig,
        TriangularLeg,
        TriangularPath,
        TriangularPosition,
    )
except ImportError:
    class TriangularExecutor(BaseExecutor):
        pass
    class TriangularConfig:
        pass
    class TriangularLeg:
        pass
    class TriangularPath:
        pass
    class TriangularPosition:
        pass

# Import factory
from .executor_factory import (
    ExecutorFactory,
    ExecutorRegistry as FactoryRegistry,
    ExecutorType,
    ExecutorMetadata,
    ExecutorCreationParams,
    create_executor,
    create_executor_from_config,
    list_executor_types,
    get_executor as factory_get_executor,
    register_executor_instance,
    remove_executor_instance,
)

# Logger setup
logger = logging.getLogger(__name__)

# Version information
__version__ = "4.2.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Package metadata
PACKAGE_METADATA = {
    "name": "executors",
    "version": __version__,
    "description": "Complete Execution Engine Suite",
    "author": __author__,
    "copyright": __copyright__,
    "executors_count": 14,
    "supported_executors": [
        "batch",
        "cross_exchange",
        "cross_chain",
        "dex",
        "flash_loan",
        "futures_spot",
        "mixed",
        "order",
        "parallel",
        "sequential",
        "smart",
        "statistical",
        "triangular",
    ],
    "supported_execution_types": [
        "atomic",
        "sequential",
        "parallel",
        "batch",
        "smart",
        "flash_loan",
        "dex",
        "cross_exchange",
        "cross_chain",
        "statistical",
        "triangular",
    ],
    "supported_strategies": [
        "dex_arbitrage",
        "cross_exchange_arbitrage",
        "cross_chain_arbitrage",
        "flash_loan_arbitrage",
        "futures_spot_arbitrage",
        "statistical_arbitrage",
        "triangular_arbitrage",
        "mixed_arbitrage",
        "basis_trading",
        "funding_rate_arbitrage",
    ],
}

# Public API - All executors
__all__ = [
    # Base classes
    'BaseExecutor',
    'ExecutionType',
    'ExecutionStatus',
    'ExecutionPriority',
    'ExecutionRisk',
    'ExecutionConfig',
    'ExecutionOrder',
    'ExecutionPosition',
    'ExecutionResult',
    'ExecutionPlan',
    'ExecutionListener',
    
    # Batch Executor
    'BatchExecutor',
    'BatchConfig',
    'BatchOrder',
    'BatchResult',
    
    # Cross-Exchange Executor
    'CrossExchangeExecutor',
    'CrossExchangeConfig',
    'CrossExchangeOrder',
    'CrossExchangePosition',
    
    # Cross-Chain Executor
    'CrossChainExecutor',
    'CrossChainConfig',
    'BridgeProtocol',
    'BlockchainChain',
    'BridgeTransaction',
    'CrossChainOrder',
    'CrossChainPosition',
    
    # DEX Executor
    'DEXExecutor',
    'DEXConfig',
    'DEXRoute',
    'DEXPosition',
    
    # Flash Loan Executor
    'FlashLoanExecutor',
    'FlashLoanConfig',
    'FlashLoanProtocol',
    'FlashLoanInfo',
    'FlashLoanExecution',
    'FlashLoanPosition',
    
    # Futures-Spot Executor
    'FuturesSpotExecutor',
    'FuturesSpotConfig',
    'BasisData',
    'FuturesSpotPosition',
    
    # Mixed Executor
    'MixedExecutor',
    'MixedConfig',
    'StrategyExecution',
    'MixedPosition',
    
    # Order Executor
    'OrderExecutor',
    'OrderConfig',
    'OrderExecution',
    'OrderRoute',
    'OrderResult',
    
    # Parallel Executor
    'ParallelExecutor',
    'ParallelConfig',
    'ParallelTask',
    'ParallelResult',
    
    # Sequential Executor
    'SequentialExecutor',
    'SequentialConfig',
    'Step',
    'SequentialResult',
    
    # Smart Executor
    'SmartExecutor',
    'SmartConfig',
    'ExecutionStrategy',
    'StrategyScore',
    'MarketCondition',
    'StrategyRecommendation',
    
    # Statistical Executor
    'StatisticalExecutor',
    'StatisticalConfig',
    'StatisticalPair',
    'StatisticalPosition',
    
    # Triangular Executor
    'TriangularExecutor',
    'TriangularConfig',
    'TriangularLeg',
    'TriangularPath',
    'TriangularPosition',
    
    # Factory
    'ExecutorFactory',
    'FactoryRegistry',
    'ExecutorType',
    'ExecutorMetadata',
    'ExecutorCreationParams',
    'create_executor',
    'create_executor_from_config',
    'list_executor_types',
    'factory_get_executor',
    'register_executor_instance',
    'remove_executor_instance',
    
    # Registry
    'ExecutorRegistry',
    'ExecutorEvent',
    'ExecutorEventType',
    
    # Metadata
    'PACKAGE_METADATA',
    'get_version',
    'get_metadata',
    'list_executors',
    'get_executor',
    'get_all_executors',
]


class ExecutorEventType(Enum):
    """Executor event types."""
    STARTED = "started"
    STOPPED = "stopped"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_PROGRESS = "execution_progress"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    STRATEGY_SELECTED = "strategy_selected"
    STRATEGY_CHANGED = "strategy_changed"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    METRICS_UPDATED = "metrics_updated"


@dataclass
class ExecutorEvent:
    """Executor event."""
    event_type: ExecutorEventType
    executor_name: str
    execution_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None


class ExecutorRegistry:
    """
    Registry for managing all executor instances.
    
    This class provides centralized management of executor instances,
    including creation, configuration, and lifecycle management.
    
    Features:
    - Singleton pattern for global access
    - Executor registration and retrieval
    - Lifecycle management (start/stop)
    - Event system for executor notifications
    - Metrics aggregation
    - Health monitoring
    """
    
    _instance = None
    _executors: Dict[str, BaseExecutor] = {}
    _configs: Dict[str, ExecutionConfig] = {}
    _listeners: List[Callable[[ExecutorEvent], None]] = []
    _event_history: List[ExecutorEvent] = []
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
            self._executor_metadata = {}
            self._register_executor_metadata()
            self.logger.info("ExecutorRegistry initialized")
    
    def _register_executor_metadata(self) -> None:
        """Register metadata for all executors."""
        self._executor_metadata = {
            "batch": {
                "name": "Batch Executor",
                "description": "Batch execution engine for grouped orders",
                "supported_strategies": ["dex", "cross_exchange", "mixed"],
                "priority": 1,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
            "cross_exchange": {
                "name": "Cross-Exchange Executor",
                "description": "Cross-exchange arbitrage execution engine",
                "supported_strategies": ["cross_exchange"],
                "priority": 1,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
            "cross_chain": {
                "name": "Cross-Chain Executor",
                "description": "Cross-chain arbitrage execution engine",
                "supported_strategies": ["cross_chain"],
                "priority": 2,
                "requires_exchanges": True,
                "requires_web3": True,
                "is_experimental": True,
            },
            "dex": {
                "name": "DEX Executor",
                "description": "DEX execution engine for on-chain swaps",
                "supported_strategies": ["dex"],
                "priority": 1,
                "requires_exchanges": True,
                "requires_web3": True,
                "is_experimental": False,
            },
            "flash_loan": {
                "name": "Flash Loan Executor",
                "description": "Flash loan execution engine",
                "supported_strategies": ["flash_loan"],
                "priority": 2,
                "requires_exchanges": True,
                "requires_web3": True,
                "is_experimental": True,
            },
            "futures_spot": {
                "name": "Futures-Spot Executor",
                "description": "Futures-spot arbitrage execution engine",
                "supported_strategies": ["futures_spot"],
                "priority": 1,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
            "mixed": {
                "name": "Mixed Executor",
                "description": "Mixed strategy execution engine",
                "supported_strategies": ["mixed", "composite"],
                "priority": 2,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
            "order": {
                "name": "Order Executor",
                "description": "Order execution engine",
                "supported_strategies": ["all"],
                "priority": 1,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
            "parallel": {
                "name": "Parallel Executor",
                "description": "Parallel execution engine",
                "supported_strategies": ["all"],
                "priority": 1,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
            "sequential": {
                "name": "Sequential Executor",
                "description": "Sequential execution engine",
                "supported_strategies": ["all"],
                "priority": 1,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
            "smart": {
                "name": "Smart Executor",
                "description": "Smart execution engine with dynamic strategy selection",
                "supported_strategies": ["all"],
                "priority": 1,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
            "statistical": {
                "name": "Statistical Executor",
                "description": "Statistical arbitrage execution engine",
                "supported_strategies": ["statistical"],
                "priority": 2,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
            "triangular": {
                "name": "Triangular Executor",
                "description": "Triangular arbitrage execution engine",
                "supported_strategies": ["triangular"],
                "priority": 2,
                "requires_exchanges": True,
                "requires_web3": False,
                "is_experimental": False,
            },
        }
    
    def register_executor(
        self,
        name: str,
        executor: BaseExecutor,
        config: Optional[ExecutionConfig] = None
    ) -> None:
        """
        Register an executor instance.
        
        Args:
            name: Executor name
            executor: Executor instance
            config: Optional configuration
        """
        with self._lock:
            self._executors[name] = executor
            if config:
                self._configs[name] = config
            self._emit_event(ExecutorEventType.STARTED, name)
            self.logger.info(f"Registered executor: {name}")
    
    def unregister_executor(self, name: str) -> None:
        """
        Unregister an executor instance.
        
        Args:
            name: Executor name
        """
        with self._lock:
            if name in self._executors:
                try:
                    if hasattr(self._executors[name], 'stop'):
                        self._executors[name].stop()
                except Exception as e:
                    self.logger.error(f"Error stopping {name}: {e}")
                del self._executors[name]
                if name in self._configs:
                    del self._configs[name]
                self._emit_event(ExecutorEventType.STOPPED, name)
                self.logger.info(f"Unregistered executor: {name}")
    
    def get_executor(self, name: str) -> Optional[BaseExecutor]:
        """
        Get an executor by name.
        
        Args:
            name: Executor name
            
        Returns:
            Executor instance or None
        """
        with self._lock:
            return self._executors.get(name)
    
    def get_all_executors(self) -> Dict[str, BaseExecutor]:
        """
        Get all registered executors.
        
        Returns:
            Dictionary of executor name to instance
        """
        with self._lock:
            return self._executors.copy()
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for an executor.
        
        Args:
            name: Executor name
            
        Returns:
            Metadata dictionary or None
        """
        return self._executor_metadata.get(name)
    
    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for all executors.
        
        Returns:
            Dictionary of executor name to metadata
        """
        return self._executor_metadata.copy()
    
    def start_all(self) -> Dict[str, bool]:
        """
        Start all registered executors.
        
        Returns:
            Dictionary of executor name to success status
        """
        results = {}
        for name, executor in self._executors.items():
            try:
                if hasattr(executor, 'start'):
                    executor.start()
                    results[name] = True
                    self._emit_event(ExecutorEventType.STARTED, name)
                    self.logger.info(f"Started executor: {name}")
                else:
                    results[name] = False
                    self.logger.warning(f"Executor {name} has no start method")
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to start {name}: {e}")
                self._emit_event(ExecutorEventType.ERROR, name, error=e)
        return results
    
    def stop_all(self) -> Dict[str, bool]:
        """
        Stop all registered executors.
        
        Returns:
            Dictionary of executor name to success status
        """
        results = {}
        for name, executor in self._executors.items():
            try:
                if hasattr(executor, 'stop'):
                    executor.stop()
                    results[name] = True
                    self._emit_event(ExecutorEventType.STOPPED, name)
                    self.logger.info(f"Stopped executor: {name}")
                else:
                    results[name] = False
                    self.logger.warning(f"Executor {name} has no stop method")
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to stop {name}: {e}")
                self._emit_event(ExecutorEventType.ERROR, name, error=e)
        return results
    
    def pause_all(self) -> Dict[str, bool]:
        """
        Pause all registered executors.
        
        Returns:
            Dictionary of executor name to success status
        """
        results = {}
        for name, executor in self._executors.items():
            try:
                if hasattr(executor, 'pause'):
                    executor.pause()
                    results[name] = True
                    self.logger.info(f"Paused executor: {name}")
                else:
                    results[name] = False
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to pause {name}: {e}")
        return results
    
    def resume_all(self) -> Dict[str, bool]:
        """
        Resume all registered executors.
        
        Returns:
            Dictionary of executor name to success status
        """
        results = {}
        for name, executor in self._executors.items():
            try:
                if hasattr(executor, 'resume'):
                    executor.resume()
                    results[name] = True
                    self.logger.info(f"Resumed executor: {name}")
                else:
                    results[name] = False
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to resume {name}: {e}")
        return results
    
    def add_listener(self, listener: Callable[[ExecutorEvent], None]) -> None:
        """
        Add an event listener.
        
        Args:
            listener: Callback function for events
        """
        with self._lock:
            self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[ExecutorEvent], None]) -> None:
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
        event_type: ExecutorEventType,
        executor_name: str,
        execution_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ) -> None:
        """
        Emit an event to all listeners.
        
        Args:
            event_type: Type of event
            executor_name: Name of the executor
            execution_id: Optional execution ID
            data: Optional event data
            error: Optional error
        """
        event = ExecutorEvent(
            event_type=event_type,
            executor_name=executor_name,
            execution_id=execution_id,
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
        executor_name: Optional[str] = None,
        event_type: Optional[ExecutorEventType] = None
    ) -> List[ExecutorEvent]:
        """
        Get event history.
        
        Args:
            limit: Maximum number of events
            executor_name: Filter by executor name
            event_type: Filter by event type
            
        Returns:
            List of events
        """
        with self._lock:
            events = self._event_history.copy()
        
        if executor_name:
            events = [e for e in events if e.executor_name == executor_name]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics from all executors.
        
        Returns:
            Aggregated metrics dictionary
        """
        aggregated = {
            "total_executors": len(self._executors),
            "active_executors": 0,
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "total_errors": 0,
            "executors": {},
        }
        
        for name, executor in self._executors.items():
            try:
                if hasattr(executor, 'get_metrics'):
                    metrics = executor.get_metrics()
                    if metrics:
                        aggregated["executors"][name] = metrics
                        if metrics.get("is_running", False):
                            aggregated["active_executors"] += 1
                        aggregated["total_executions"] += metrics.get("executions_total", 0)
                        aggregated["successful_executions"] += metrics.get("executions_succeeded", 0)
                        aggregated["failed_executions"] += metrics.get("executions_failed", 0)
                        aggregated["total_profit"] += Decimal(str(metrics.get("total_profit", 0)))
                        aggregated["total_loss"] += Decimal(str(metrics.get("total_loss", 0)))
                        aggregated["net_profit"] += Decimal(str(metrics.get("net_profit", 0)))
                        aggregated["total_errors"] += metrics.get("errors", 0)
            except Exception as e:
                self.logger.error(f"Error getting metrics for {name}: {e}")
        
        return aggregated
    
    def get_healthy_executors(self) -> List[str]:
        """
        Get list of healthy executors.
        
        Returns:
            List of executor names
        """
        healthy = []
        for name, executor in self._executors.items():
            try:
                if hasattr(executor, 'get_metrics'):
                    metrics = executor.get_metrics()
                    if metrics and metrics.get("is_running", False):
                        healthy.append(name)
            except Exception:
                pass
        return healthy


# Global registry instance
executor_registry = ExecutorRegistry()


# Utility functions
def get_executor(name: str) -> Optional[BaseExecutor]:
    """
    Get an executor by name from the registry.
    
    Args:
        name: Executor name
        
    Returns:
        Executor instance or None
    """
    return executor_registry.get_executor(name)


def get_all_executors() -> Dict[str, BaseExecutor]:
    """
    Get all executors from the registry.
    
    Returns:
        Dictionary of executor name to instance
    """
    return executor_registry.get_all_executors()


def create_executor(
    executor_type: Union[str, ExecutorType],
    config: Optional[Dict[str, Any]] = None
) -> Optional[BaseExecutor]:
    """
    Create an executor using the factory.
    
    Args:
        executor_type: Type of executor to create
        config: Optional configuration
        
    Returns:
        Executor instance or None
    """
    return ExecutorFactory.create_executor_from_config(executor_type, config or {})


def list_executors() -> List[str]:
    """
    List all available executor types.
    
    Returns:
        List of executor type names
    """
    return [e.value for e in list_executor_types()]


def get_version() -> str:
    """Get package version."""
    return __version__


def get_metadata() -> Dict[str, Any]:
    """Get package metadata."""
    return PACKAGE_METADATA


def start_all_executors() -> Dict[str, bool]:
    """
    Start all registered executors.
    
    Returns:
        Dictionary of executor name to success status
    """
    return executor_registry.start_all()


def stop_all_executors() -> Dict[str, bool]:
    """
    Stop all registered executors.
    
    Returns:
        Dictionary of executor name to success status
    """
    return executor_registry.stop_all()


def pause_all_executors() -> Dict[str, bool]:
    """
    Pause all registered executors.
    
    Returns:
        Dictionary of executor name to success status
    """
    return executor_registry.pause_all()


def resume_all_executors() -> Dict[str, bool]:
    """
    Resume all registered executors.
    
    Returns:
        Dictionary of executor name to success status
    """
    return executor_registry.resume_all()


def get_aggregated_metrics() -> Dict[str, Any]:
    """
    Get aggregated metrics from all executors.
    
    Returns:
        Aggregated metrics dictionary
    """
    return executor_registry.get_aggregated_metrics()


def get_healthy_executors() -> List[str]:
    """
    Get list of healthy executors.
    
    Returns:
        List of executor names
    """
    return executor_registry.get_healthy_executors()


def add_executor_listener(listener: Callable[[ExecutorEvent], None]) -> None:
    """
    Add an executor event listener.
    
    Args:
        listener: Callback function for events
    """
    executor_registry.add_listener(listener)


def remove_executor_listener(listener: Callable[[ExecutorEvent], None]) -> None:
    """
    Remove an executor event listener.
    
    Args:
        listener: Callback function to remove
    """
    executor_registry.remove_listener(listener)


# Context manager for executor lifecycle
@contextmanager
def executor_context(executor_name: str, config: Optional[Dict[str, Any]] = None):
    """
    Context manager for executor lifecycle.
    
    Args:
        executor_name: Name of the executor
        config: Optional configuration
        
    Yields:
        Executor instance
    """
    executor = create_executor(executor_name, config)
    if not executor:
        raise ValueError(f"Failed to create executor: {executor_name}")
    
    try:
        if hasattr(executor, 'start'):
            executor.start()
        yield executor
    finally:
        if hasattr(executor, 'stop'):
            executor.stop()


# Package initialization
logger.info(f"Initializing Executors Package v{__version__}")
logger.info(f"Registered {len(executor_registry.get_all_metadata())} executor types")
logger.info(f"Package metadata: {PACKAGE_METADATA}")

# Auto-register available executors
try:
    for executor_type in ['order', 'sequential', 'parallel', 'smart']:
        try:
            executor = create_executor(executor_type)
            if executor:
                executor_registry.register_executor(executor_type, executor)
        except Exception as e:
            logger.debug(f"Failed to auto-register {executor_type}: {e}")
except Exception as e:
    logger.debug(f"Auto-registration failed: {e}")


# Lazy imports for circular dependency resolution
def __getattr__(name: str) -> Any:
    """
    Lazy import for submodules.
    
    This allows for clean imports while avoiding circular dependencies.
    """
    if name in ['batch_executor', 'cross_exchange_executor', 'cross_chain_executor',
                'dex_executor', 'flash_loan_executor', 'futures_spot_executor',
                'mixed_executor', 'order_executor', 'parallel_executor',
                'sequential_executor', 'smart_executor', 'statistical_executor',
                'triangular_executor', 'base_executor', 'executor_factory']:
        raise AttributeError(f"Module {name} not loaded. Please import directly.")
    raise AttributeError(f"module {__name__} has no attribute {name}")
