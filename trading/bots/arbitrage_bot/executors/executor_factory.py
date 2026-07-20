# trading/bots/arbitrage_bot/executors/executor_factory.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Executor Factory

"""
Executor Factory - Dynamic Executor Creation and Management

This module provides a factory pattern implementation for creating
and managing different types of execution engines in the NEXUS AI
Trading System. It supports dynamic instantiation of executors based
on strategy type, configuration, and runtime requirements.

Architecture:
    - ExecutorFactory: Main factory class
    - ExecutorRegistry: Registry of available executors
    - ExecutorType: Enumeration of executor types
    - Factory Pattern: Dynamic instantiation
    - Singleton Registry: Global access

Executor Types:
    - ATOMIC: Atomic execution (all-or-nothing)
    - SEQUENTIAL: Sequential execution (step by step)
    - PARALLEL: Parallel execution (simultaneous)
    - BATCH: Batch execution (grouped)
    - SMART: Smart execution (dynamic routing)
    - CROSS_EXCHANGE: Cross-exchange execution
    - CROSS_CHAIN: Cross-chain execution
    - DEX: DEX execution
    - FLASH_LOAN: Flash loan execution
    - MIXED: Mixed strategy execution
"""

import logging
from typing import Dict, List, Optional, Type, Any, Union, Tuple, Callable
from enum import Enum
from dataclasses import dataclass, field

from .base_executor import (
    BaseExecutor,
    ExecutionConfig,
    ExecutionType,
    ExecutionPriority,
    ExecutionRisk,
    ExecutionPlan,
    ExecutionResult,
    ExecutionListener,
)
from .batch_executor import BatchExecutor, BatchConfig
from .cross_exchange_executor import CrossExchangeExecutor, CrossExchangeConfig
from .cross_chain_executor import CrossChainExecutor, CrossChainConfig
from .dex_executor import DEXExecutor, DEXConfig
from .flash_loan_executor import FlashLoanExecutor, FlashLoanConfig
from .mixed_executor import MixedExecutor, MixedConfig
from .smart_executor import SmartExecutor, SmartConfig

from ..exchanges.base_exchange import BaseExchange, ExchangeType, ExchangeConfig


class ExecutorType(Enum):
    """Executor type enumeration."""
    ATOMIC = "atomic"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    BATCH = "batch"
    SMART = "smart"
    CROSS_EXCHANGE = "cross_exchange"
    CROSS_CHAIN = "cross_chain"
    DEX = "dex"
    FLASH_LOAN = "flash_loan"
    MIXED = "mixed"


@dataclass
class ExecutorMetadata:
    """Executor metadata."""
    executor_type: ExecutorType
    description: str
    supported_strategies: List[str]
    requires_web3: bool = False
    requires_private_key: bool = False
    requires_multiple_exchanges: bool = False
    requires_cross_chain: bool = False
    priority: int = 1
    is_experimental: bool = False


@dataclass
class ExecutorCreationParams:
    """Parameters for creating an executor."""
    executor_type: Union[str, ExecutorType]
    execution_config: Optional[Dict[str, Any]] = None
    exchange_configs: Optional[Dict[str, Dict[str, Any]]] = None
    exchanges: Optional[Dict[ExchangeType, BaseExchange]] = None
    private_key: Optional[str] = None
    web3_provider: Optional[str] = None
    batch_config: Optional[Dict[str, Any]] = None
    cross_exchange_config: Optional[Dict[str, Any]] = None
    cross_chain_config: Optional[Dict[str, Any]] = None
    dex_config: Optional[Dict[str, Any]] = None
    flash_loan_config: Optional[Dict[str, Any]] = None
    mixed_config: Optional[Dict[str, Any]] = None
    smart_config: Optional[Dict[str, Any]] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


class ExecutorRegistry:
    """
    Registry for executor types and their metadata.
    
    Features:
    - Register executor types
    - Query executor metadata
    - List available executors
    - Validate executor configurations
    """
    
    _instance = None
    _executors: Dict[ExecutorType, Type[BaseExecutor]] = {}
    _metadata: Dict[ExecutorType, ExecutorMetadata] = {}
    
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
            self._register_default_executors()
            self.logger.info("ExecutorRegistry initialized")
    
    def _register_default_executors(self) -> None:
        """Register default executor types."""
        # Batch Executor
        self.register_executor(
            ExecutorType.BATCH,
            BatchExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.BATCH,
                description="Batch execution engine for grouped orders",
                supported_strategies=["dex", "cross_exchange", "mixed"],
                requires_private_key=True,
                requires_multiple_exchanges=True,
                priority=1,
            )
        )
        
        # Cross-Exchange Executor
        self.register_executor(
            ExecutorType.CROSS_EXCHANGE,
            CrossExchangeExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.CROSS_EXCHANGE,
                description="Cross-exchange arbitrage execution engine",
                supported_strategies=["cross_exchange"],
                requires_private_key=True,
                requires_multiple_exchanges=True,
                priority=1,
            )
        )
        
        # Cross-Chain Executor
        self.register_executor(
            ExecutorType.CROSS_CHAIN,
            CrossChainExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.CROSS_CHAIN,
                description="Cross-chain arbitrage execution engine",
                supported_strategies=["cross_chain"],
                requires_private_key=True,
                requires_web3=True,
                requires_cross_chain=True,
                priority=2,
                is_experimental=True,
            )
        )
        
        # DEX Executor
        self.register_executor(
            ExecutorType.DEX,
            DEXExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.DEX,
                description="DEX execution engine for on-chain swaps",
                supported_strategies=["dex"],
                requires_private_key=True,
                requires_web3=True,
                priority=1,
            )
        )
        
        # Flash Loan Executor
        self.register_executor(
            ExecutorType.FLASH_LOAN,
            FlashLoanExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.FLASH_LOAN,
                description="Flash loan execution engine",
                supported_strategies=["flash_loan"],
                requires_private_key=True,
                requires_web3=True,
                priority=2,
                is_experimental=True,
            )
        )
        
        # Mixed Executor
        self.register_executor(
            ExecutorType.MIXED,
            MixedExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.MIXED,
                description="Mixed strategy execution engine",
                supported_strategies=["mixed", "composite"],
                requires_private_key=True,
                requires_multiple_exchanges=True,
                priority=2,
            )
        )
        
        # Smart Executor
        self.register_executor(
            ExecutorType.SMART,
            SmartExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.SMART,
                description="Smart execution engine with dynamic routing",
                supported_strategies=["all"],
                requires_private_key=True,
                requires_multiple_exchanges=True,
                priority=1,
            )
        )
        
        # Atomic Executor (alias for Smart with atomic execution)
        self.register_executor(
            ExecutorType.ATOMIC,
            SmartExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.ATOMIC,
                description="Atomic execution engine (all-or-nothing)",
                supported_strategies=["all"],
                requires_private_key=True,
                requires_multiple_exchanges=True,
                priority=1,
            )
        )
        
        # Sequential Executor (alias for Smart with sequential execution)
        self.register_executor(
            ExecutorType.SEQUENTIAL,
            SmartExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.SEQUENTIAL,
                description="Sequential execution engine",
                supported_strategies=["all"],
                requires_private_key=True,
                requires_multiple_exchanges=True,
                priority=2,
            )
        )
        
        # Parallel Executor (alias for Smart with parallel execution)
        self.register_executor(
            ExecutorType.PARALLEL,
            SmartExecutor,
            ExecutorMetadata(
                executor_type=ExecutorType.PARALLEL,
                description="Parallel execution engine",
                supported_strategies=["all"],
                requires_private_key=True,
                requires_multiple_exchanges=True,
                priority=2,
            )
        )
    
    def register_executor(
        self,
        executor_type: ExecutorType,
        executor_class: Type[BaseExecutor],
        metadata: ExecutorMetadata,
    ) -> None:
        """
        Register an executor type.
        
        Args:
            executor_type: Executor type
            executor_class: Executor class
            metadata: Executor metadata
        """
        self._executors[executor_type] = executor_class
        self._metadata[executor_type] = metadata
        self.logger.info(f"Registered executor: {executor_type.value}")
    
    def get_executor_class(self, executor_type: ExecutorType) -> Optional[Type[BaseExecutor]]:
        """
        Get executor class by type.
        
        Args:
            executor_type: Executor type
            
        Returns:
            Executor class or None
        """
        return self._executors.get(executor_type)
    
    def get_metadata(self, executor_type: ExecutorType) -> Optional[ExecutorMetadata]:
        """
        Get executor metadata.
        
        Args:
            executor_type: Executor type
            
        Returns:
            ExecutorMetadata or None
        """
        return self._metadata.get(executor_type)
    
    def list_executors(self) -> List[ExecutorType]:
        """
        List all registered executor types.
        
        Returns:
            List of executor types
        """
        return list(self._executors.keys())
    
    def list_active_executors(self) -> List[ExecutorType]:
        """
        List all active (non-experimental) executor types.
        
        Returns:
            List of executor types
        """
        return [e for e, m in self._metadata.items() if not m.is_experimental]
    
    def get_supported_strategies(self, executor_type: ExecutorType) -> List[str]:
        """
        Get strategies supported by an executor.
        
        Args:
            executor_type: Executor type
            
        Returns:
            List of strategy names
        """
        metadata = self._metadata.get(executor_type)
        return metadata.supported_strategies if metadata else []
    
    def find_executor_for_strategy(
        self,
        strategy: str,
        prefer_active: bool = True,
    ) -> Optional[ExecutorType]:
        """
        Find an executor that supports a strategy.
        
        Args:
            strategy: Strategy name
            prefer_active: Prefer active (non-experimental) executors
            
        Returns:
            ExecutorType or None
        """
        candidates = []
        
        for executor_type, metadata in self._metadata.items():
            if strategy in metadata.supported_strategies:
                if prefer_active and metadata.is_experimental:
                    continue
                candidates.append((executor_type, metadata.priority))
        
        if not candidates:
            return None
        
        # Sort by priority (lower is better)
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]
    
    def is_valid_executor(self, executor_type: ExecutorType) -> bool:
        """
        Check if an executor type is valid.
        
        Args:
            executor_type: Executor type
            
        Returns:
            True if valid
        """
        return executor_type in self._executors


class ExecutorFactory:
    """
    Factory for creating executor instances.
    
    Features:
    - Dynamic executor creation
    - Configuration validation
    - Automatic dependency injection
    - Executor caching
    - Instance management
    """
    
    _instance = None
    _executor_instances: Dict[str, BaseExecutor] = {}
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the factory."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.logger = logging.getLogger(f"{__name__}.Factory")
            self.registry = ExecutorRegistry()
            self.logger.info("ExecutorFactory initialized")
    
    @classmethod
    def create_executor(
        cls,
        params: ExecutorCreationParams,
    ) -> Optional[BaseExecutor]:
        """
        Create an executor instance.
        
        Args:
            params: Executor creation parameters
            
        Returns:
            Executor instance or None
        """
        factory = cls._get_instance()
        return factory._create_executor(params)
    
    @classmethod
    def create_executor_from_config(
        cls,
        executor_type: Union[str, ExecutorType],
        config: Dict[str, Any],
    ) -> Optional[BaseExecutor]:
        """
        Create an executor from configuration.
        
        Args:
            executor_type: Executor type
            config: Configuration dictionary
            
        Returns:
            Executor instance or None
        """
        # Parse executor type
        if isinstance(executor_type, str):
            try:
                executor_type = ExecutorType(executor_type.lower())
            except ValueError:
                # Try to find matching executor type
                executor_type = cls._find_matching_executor(executor_type)
                if not executor_type:
                    return None
        
        # Build creation parameters
        params = ExecutorCreationParams(
            executor_type=executor_type,
            execution_config=config.get("execution_config"),
            exchange_configs=config.get("exchange_configs"),
            private_key=config.get("private_key"),
            web3_provider=config.get("web3_provider"),
            batch_config=config.get("batch_config"),
            cross_exchange_config=config.get("cross_exchange_config"),
            cross_chain_config=config.get("cross_chain_config"),
            dex_config=config.get("dex_config"),
            flash_loan_config=config.get("flash_loan_config"),
            mixed_config=config.get("mixed_config"),
            smart_config=config.get("smart_config"),
            extra_params=config.get("extra_params", {}),
        )
        
        return cls.create_executor(params)
    
    @classmethod
    def get_executor(
        cls,
        executor_id: str,
    ) -> Optional[BaseExecutor]:
        """
        Get a cached executor instance.
        
        Args:
            executor_id: Executor ID
            
        Returns:
            Executor instance or None
        """
        factory = cls._get_instance()
        return factory._executor_instances.get(executor_id)
    
    @classmethod
    def register_executor_instance(
        cls,
        executor_id: str,
        executor: BaseExecutor,
    ) -> None:
        """
        Register an executor instance.
        
        Args:
            executor_id: Executor ID
            executor: Executor instance
        """
        factory = cls._get_instance()
        factory._executor_instances[executor_id] = executor
        factory.logger.info(f"Registered executor instance: {executor_id}")
    
    @classmethod
    def remove_executor_instance(cls, executor_id: str) -> bool:
        """
        Remove an executor instance.
        
        Args:
            executor_id: Executor ID
            
        Returns:
            True if removed
        """
        factory = cls._get_instance()
        if executor_id in factory._executor_instances:
            del factory._executor_instances[executor_id]
            factory.logger.info(f"Removed executor instance: {executor_id}")
            return True
        return False
    
    @classmethod
    def list_executor_types(cls) -> List[ExecutorType]:
        """
        List all available executor types.
        
        Returns:
            List of executor types
        """
        factory = cls._get_instance()
        return factory.registry.list_executors()
    
    @classmethod
    def list_executor_instances(cls) -> List[str]:
        """
        List all registered executor instances.
        
        Returns:
            List of executor IDs
        """
        factory = cls._get_instance()
        return list(factory._executor_instances.keys())
    
    @classmethod
    def _get_instance(cls) -> "ExecutorFactory":
        """Get or create factory instance."""
        if cls._instance is None:
            cls._instance = ExecutorFactory()
        return cls._instance
    
    def _create_executor(self, params: ExecutorCreationParams) -> Optional[BaseExecutor]:
        """
        Internal method for creating an executor.
        
        Args:
            params: Executor creation parameters
            
        Returns:
            Executor instance or None
        """
        try:
            # Get executor class
            executor_type = params.executor_type
            if isinstance(executor_type, str):
                try:
                    executor_type = ExecutorType(executor_type.lower())
                except ValueError:
                    executor_type = self._find_matching_executor(executor_type)
                    if not executor_type:
                        self.logger.error(f"Unknown executor type: {params.executor_type}")
                        return None
            
            executor_class = self.registry.get_executor_class(executor_type)
            if not executor_class:
                self.logger.error(f"Executor not found: {executor_type}")
                return None
            
            # Build execution config
            exec_config = self._build_execution_config(params.execution_config)
            
            # Build exchange instances
            exchanges = self._build_exchanges(params)
            
            # Create executor based on type
            if executor_type == ExecutorType.BATCH:
                batch_config = self._build_batch_config(params.batch_config)
                return BatchExecutor(exec_config, exchanges, batch_config)
            
            elif executor_type == ExecutorType.CROSS_EXCHANGE:
                cross_exchange_config = self._build_cross_exchange_config(
                    params.cross_exchange_config
                )
                return CrossExchangeExecutor(exec_config, exchanges, cross_exchange_config)
            
            elif executor_type == ExecutorType.CROSS_CHAIN:
                cross_chain_config = self._build_cross_chain_config(
                    params.cross_chain_config
                )
                return CrossChainExecutor(
                    exec_config,
                    exchanges,
                    cross_chain_config,
                    params.private_key,
                    params.web3_provider,
                )
            
            elif executor_type == ExecutorType.DEX:
                dex_config = self._build_dex_config(params.dex_config)
                return DEXExecutor(
                    exec_config,
                    exchanges,
                    dex_config,
                    params.private_key,
                    params.web3_provider,
                )
            
            elif executor_type == ExecutorType.FLASH_LOAN:
                flash_loan_config = self._build_flash_loan_config(
                    params.flash_loan_config
                )
                return FlashLoanExecutor(
                    exec_config,
                    exchanges,
                    flash_loan_config,
                    params.private_key,
                    params.web3_provider,
                )
            
            elif executor_type == ExecutorType.MIXED:
                mixed_config = self._build_mixed_config(params.mixed_config)
                return MixedExecutor(
                    exec_config,
                    exchanges,
                    mixed_config,
                    params.private_key,
                    params.web3_provider,
                )
            
            elif executor_type in [
                ExecutorType.SMART,
                ExecutorType.ATOMIC,
                ExecutorType.SEQUENTIAL,
                ExecutorType.PARALLEL,
            ]:
                smart_config = self._build_smart_config(params.smart_config, executor_type)
                return SmartExecutor(exec_config, exchanges, smart_config)
            
            else:
                self.logger.error(f"Unsupported executor type: {executor_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Executor creation failed: {e}")
            return None
    
    def _build_execution_config(
        self,
        config: Optional[Dict[str, Any]],
    ) -> ExecutionConfig:
        """Build execution configuration."""
        if config:
            return ExecutionConfig(**config)
        return ExecutionConfig()
    
    def _build_exchanges(
        self,
        params: ExecutorCreationParams,
    ) -> Dict[ExchangeType, BaseExchange]:
        """Build exchange instances."""
        exchanges = {}
        
        if params.exchanges:
            return params.exchanges
        
        if params.exchange_configs:
            from ..exchanges.exchange_factory import ExchangeFactory
            
            for exchange_type, exchange_config in params.exchange_configs.items():
                try:
                    exchange = ExchangeFactory.create_exchange(
                        exchange_type,
                        exchange_config
                    )
                    if exchange:
                        exchanges[ExchangeType(exchange_type)] = exchange
                except Exception as e:
                    self.logger.error(f"Failed to create exchange {exchange_type}: {e}")
        
        return exchanges
    
    def _build_batch_config(self, config: Optional[Dict[str, Any]]) -> BatchConfig:
        """Build batch configuration."""
        if config:
            return BatchConfig(**config)
        return BatchConfig()
    
    def _build_cross_exchange_config(
        self,
        config: Optional[Dict[str, Any]],
    ) -> CrossExchangeConfig:
        """Build cross-exchange configuration."""
        if config:
            return CrossExchangeConfig(**config)
        return CrossExchangeConfig()
    
    def _build_cross_chain_config(
        self,
        config: Optional[Dict[str, Any]],
    ) -> CrossChainConfig:
        """Build cross-chain configuration."""
        if config:
            return CrossChainConfig(**config)
        return CrossChainConfig()
    
    def _build_dex_config(self, config: Optional[Dict[str, Any]]) -> DEXConfig:
        """Build DEX configuration."""
        if config:
            return DEXConfig(**config)
        return DEXConfig()
    
    def _build_flash_loan_config(
        self,
        config: Optional[Dict[str, Any]],
    ) -> FlashLoanConfig:
        """Build flash loan configuration."""
        if config:
            return FlashLoanConfig(**config)
        return FlashLoanConfig()
    
    def _build_mixed_config(self, config: Optional[Dict[str, Any]]) -> MixedConfig:
        """Build mixed configuration."""
        if config:
            return MixedConfig(**config)
        return MixedConfig()
    
    def _build_smart_config(
        self,
        config: Optional[Dict[str, Any]],
        executor_type: ExecutorType,
    ) -> SmartConfig:
        """Build smart configuration."""
        smart_config = SmartConfig()
        if config:
            for key, value in config.items():
                setattr(smart_config, key, value)
        
        # Set execution type based on executor type
        if executor_type == ExecutorType.ATOMIC:
            smart_config.execution_type = ExecutionType.ATOMIC
        elif executor_type == ExecutorType.SEQUENTIAL:
            smart_config.execution_type = ExecutionType.SEQUENTIAL
        elif executor_type == ExecutorType.PARALLEL:
            smart_config.execution_type = ExecutionType.PARALLEL
        else:
            smart_config.execution_type = ExecutionType.SMART
        
        return smart_config
    
    def _find_matching_executor(
        self,
        executor_type_str: str,
    ) -> Optional[ExecutorType]:
        """Find matching executor type from string."""
        executor_type_str = executor_type_str.lower()
        for executor_type in self.registry.list_executors():
            if executor_type.value == executor_type_str:
                return executor_type
            if executor_type_str in executor_type.value:
                return executor_type
            if executor_type.name.lower() == executor_type_str:
                return executor_type
        return None


# Utility functions
def create_executor(params: ExecutorCreationParams) -> Optional[BaseExecutor]:
    """
    Create an executor instance.
    
    Args:
        params: Executor creation parameters
        
    Returns:
        Executor instance or None
    """
    return ExecutorFactory.create_executor(params)


def create_executor_from_config(
    executor_type: Union[str, ExecutorType],
    config: Dict[str, Any],
) -> Optional[BaseExecutor]:
    """
    Create an executor from configuration.
    
    Args:
        executor_type: Executor type
        config: Configuration dictionary
        
    Returns:
        Executor instance or None
    """
    return ExecutorFactory.create_executor_from_config(executor_type, config)


def list_executor_types() -> List[ExecutorType]:
    """
    List all available executor types.
    
    Returns:
        List of executor types
    """
    return ExecutorFactory.list_executor_types()


def get_executor(executor_id: str) -> Optional[BaseExecutor]:
    """
    Get a cached executor instance.
    
    Args:
        executor_id: Executor ID
        
    Returns:
        Executor instance or None
    """
    return ExecutorFactory.get_executor(executor_id)


def register_executor_instance(executor_id: str, executor: BaseExecutor) -> None:
    """
    Register an executor instance.
    
    Args:
        executor_id: Executor ID
        executor: Executor instance
    """
    ExecutorFactory.register_executor_instance(executor_id, executor)


def remove_executor_instance(executor_id: str) -> bool:
    """
    Remove an executor instance.
    
    Args:
        executor_id: Executor ID
        
    Returns:
        True if removed
    """
    return ExecutorFactory.remove_executor_instance(executor_id)


# Module exports
__all__ = [
    'ExecutorFactory',
    'ExecutorRegistry',
    'ExecutorType',
    'ExecutorMetadata',
    'ExecutorCreationParams',
    'create_executor',
    'create_executor_from_config',
    'list_executor_types',
    'get_executor',
    'register_executor_instance',
    'remove_executor_instance',
]
