# trading/bots/arbitrage_bot/strategies/strategy_factory.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Strategy Factory

"""
Strategy Factory - Dynamic Strategy Creation and Management

This module provides a factory pattern implementation for creating
and managing different types of trading strategies in the NEXUS AI
Trading System. It supports dynamic instantiation of strategies based
on configuration and runtime requirements.

Architecture:
    - StrategyFactory: Main factory class
    - StrategyRegistry: Registry of available strategies
    - StrategyType: Enumeration of strategy types
    - Factory Pattern: Dynamic instantiation
    - Singleton Registry: Global access

Strategy Types:
    - DEX_ARBITRAGE: DEX arbitrage strategy
    - CROSS_EXCHANGE: Cross-exchange arbitrage
    - CROSS_CHAIN: Cross-chain arbitrage
    - FLASH_LOAN: Flash loan arbitrage
    - FUTURES_SPOT: Futures-spot basis trading
    - STATISTICAL: Statistical arbitrage
    - TRIANGULAR: Triangular arbitrage
    - MOMENTUM: Momentum arbitrage
    - MIXED: Mixed strategy
    - SMART: Smart strategy selection
"""

import logging
from typing import Dict, List, Optional, Type, Any, Union, Tuple, Callable
from enum import Enum
from dataclasses import dataclass, field

from .base_strategy import BaseStrategy, StrategyConfig, StrategyType, StrategyStatus
from .momentum_arbitrage import MomentumArbitrage
from .statistical_strategy import StatisticalStrategy
# Import other strategies as they are created
# from .dex_arbitrage import DexArbitrage
# from .cross_exchange import CrossExchangeStrategy
# from .cross_chain import CrossChainStrategy
# from .flash_loan import FlashLoanStrategy
# from .futures_spot import FuturesSpotStrategy
# from .triangular import TriangularStrategy
# from .mixed import MixedStrategy
# from .smart import SmartStrategy

from ..executors.base_executor import BaseExecutor
from ..exchanges.base_exchange import BaseExchange, ExchangeType


class StrategyType(Enum):
    """Strategy type enumeration."""
    DEX_ARBITRAGE = "dex_arbitrage"
    CROSS_EXCHANGE = "cross_exchange"
    CROSS_CHAIN = "cross_chain"
    FLASH_LOAN = "flash_loan"
    FUTURES_SPOT = "futures_spot"
    STATISTICAL = "statistical"
    TRIANGULAR = "triangular"
    MOMENTUM = "momentum"
    MIXED = "mixed"
    SMART = "smart"


@dataclass
class StrategyMetadata:
    """Strategy metadata."""
    strategy_type: StrategyType
    name: str
    description: str
    supported_exchanges: List[str]
    supported_markets: List[str]
    requires_web3: bool = False
    requires_private_key: bool = False
    requires_multiple_exchanges: bool = False
    requires_cross_chain: bool = False
    priority: int = 1
    is_experimental: bool = False
    min_profit_threshold: float = 0.001
    min_confidence: float = 0.6


@dataclass
class StrategyCreationParams:
    """Parameters for creating a strategy."""
    strategy_type: Union[str, StrategyType]
    exchanges: Dict[ExchangeType, BaseExchange]
    executor: BaseExecutor
    config: Optional[Dict[str, Any]] = None
    min_profit_threshold: Optional[float] = None
    min_confidence: Optional[float] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


class StrategyRegistry:
    """
    Registry for strategy types and their metadata.
    
    Features:
    - Register strategy types
    - Query strategy metadata
    - List available strategies
    - Validate strategy configurations
    """
    
    _instance = None
    _strategies: Dict[StrategyType, Type[BaseStrategy]] = {}
    _metadata: Dict[StrategyType, StrategyMetadata] = {}
    
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
            self._register_default_strategies()
            self.logger.info("StrategyRegistry initialized")
    
    def _register_default_strategies(self) -> None:
        """Register default strategy types."""
        # Momentum Strategy
        self.register_strategy(
            StrategyType.MOMENTUM,
            MomentumArbitrage,
            StrategyMetadata(
                strategy_type=StrategyType.MOMENTUM,
                name="Momentum Arbitrage",
                description="Leverages price momentum across different markets and timeframes",
                supported_exchanges=["binance", "bybit", "okx"],
                supported_markets=["spot", "futures"],
                requires_multiple_exchanges=True,
                priority=2,
            )
        )
        
        # Statistical Strategy
        self.register_strategy(
            StrategyType.STATISTICAL,
            StatisticalStrategy,
            StrategyMetadata(
                strategy_type=StrategyType.STATISTICAL,
                name="Statistical Arbitrage",
                description="Uses cointegration and correlation analysis for mean reversion",
                supported_exchanges=["binance", "bybit", "okx"],
                supported_markets=["spot"],
                requires_multiple_exchanges=False,
                priority=2,
            )
        )
        
        # DEX Arbitrage Strategy
        # self.register_strategy(
        #     StrategyType.DEX_ARBITRAGE,
        #     DexArbitrage,
        #     StrategyMetadata(
        #         strategy_type=StrategyType.DEX_ARBITRAGE,
        #         name="DEX Arbitrage",
        #         description="Arbitrage across decentralized exchanges",
        #         supported_exchanges=["uniswap", "pancakeswap", "sushiswap"],
        #         supported_markets=["spot"],
        #         requires_web3=True,
        #         requires_private_key=True,
        #         priority=1,
        #     )
        # )
        
        # Cross-Exchange Strategy
        # self.register_strategy(
        #     StrategyType.CROSS_EXCHANGE,
        #     CrossExchangeStrategy,
        #     StrategyMetadata(
        #         strategy_type=StrategyType.CROSS_EXCHANGE,
        #         name="Cross-Exchange Arbitrage",
        #         description="Arbitrage across different centralized exchanges",
        #         supported_exchanges=["binance", "bybit", "okx", "kucoin", "mexc"],
        #         supported_markets=["spot", "futures"],
        #         requires_multiple_exchanges=True,
        #         priority=1,
        #     )
        # )
        
        # Cross-Chain Strategy
        # self.register_strategy(
        #     StrategyType.CROSS_CHAIN,
        #     CrossChainStrategy,
        #     StrategyMetadata(
        #         strategy_type=StrategyType.CROSS_CHAIN,
        #         name="Cross-Chain Arbitrage",
        #         description="Arbitrage across different blockchain networks",
        #         supported_exchanges=["uniswap", "pancakeswap"],
        #         supported_markets=["spot"],
        #         requires_web3=True,
        #         requires_private_key=True,
        #         requires_cross_chain=True,
        #         priority=3,
        #         is_experimental=True,
        #     )
        # )
        
        # Flash Loan Strategy
        # self.register_strategy(
        #     StrategyType.FLASH_LOAN,
        #     FlashLoanStrategy,
        #     StrategyMetadata(
        #         strategy_type=StrategyType.FLASH_LOAN,
        #         name="Flash Loan Arbitrage",
        #         description="Capital-efficient arbitrage using flash loans",
        #         supported_exchanges=["aave", "balancer", "uniswap"],
        #         supported_markets=["spot"],
        #         requires_web3=True,
        #         requires_private_key=True,
        #         priority=3,
        #         is_experimental=True,
        #     )
        # )
        
        # Futures-Spot Strategy
        # self.register_strategy(
        #     StrategyType.FUTURES_SPOT,
        #     FuturesSpotStrategy,
        #     StrategyMetadata(
        #         strategy_type=StrategyType.FUTURES_SPOT,
        #         name="Futures-Spot Arbitrage",
        #         description="Basis trading between futures and spot markets",
        #         supported_exchanges=["binance", "bybit", "okx"],
        #         supported_markets=["spot", "futures"],
        #         requires_multiple_exchanges=False,
        #         priority=2,
        #     )
        # )
        
        # Triangular Strategy
        # self.register_strategy(
        #     StrategyType.TRIANGULAR,
        #     TriangularStrategy,
        #     StrategyMetadata(
        #         strategy_type=StrategyType.TRIANGULAR,
        #         name="Triangular Arbitrage",
        #         description="Arbitrage across three trading pairs",
        #         supported_exchanges=["binance", "bybit", "okx"],
        #         supported_markets=["spot"],
        #         requires_multiple_exchanges=False,
        #         priority=2,
        #     )
        # )
        
        # Mixed Strategy
        # self.register_strategy(
        #     StrategyType.MIXED,
        #     MixedStrategy,
        #     StrategyMetadata(
        #         strategy_type=StrategyType.MIXED,
        #         name="Mixed Strategy",
        #         description="Combines multiple strategies for optimal results",
        #         supported_exchanges=["all"],
        #         supported_markets=["all"],
        #         requires_multiple_exchanges=True,
        #         priority=2,
        #     )
        # )
        
        # Smart Strategy
        # self.register_strategy(
        #     StrategyType.SMART,
        #     SmartStrategy,
        #     StrategyMetadata(
        #         strategy_type=StrategyType.SMART,
        #         name="Smart Strategy",
        #         description="Dynamically selects the best strategy based on market conditions",
        #         supported_exchanges=["all"],
        #         supported_markets=["all"],
        #         requires_multiple_exchanges=True,
        #         priority=1,
        #     )
        # )
    
    def register_strategy(
        self,
        strategy_type: StrategyType,
        strategy_class: Type[BaseStrategy],
        metadata: StrategyMetadata,
    ) -> None:
        """
        Register a strategy type.
        
        Args:
            strategy_type: Strategy type
            strategy_class: Strategy class
            metadata: Strategy metadata
        """
        self._strategies[strategy_type] = strategy_class
        self._metadata[strategy_type] = metadata
        self.logger.info(f"Registered strategy: {strategy_type.value}")
    
    def get_strategy_class(self, strategy_type: StrategyType) -> Optional[Type[BaseStrategy]]:
        """
        Get strategy class by type.
        
        Args:
            strategy_type: Strategy type
            
        Returns:
            Strategy class or None
        """
        return self._strategies.get(strategy_type)
    
    def get_metadata(self, strategy_type: StrategyType) -> Optional[StrategyMetadata]:
        """
        Get strategy metadata.
        
        Args:
            strategy_type: Strategy type
            
        Returns:
            StrategyMetadata or None
        """
        return self._metadata.get(strategy_type)
    
    def list_strategies(self) -> List[StrategyType]:
        """
        List all registered strategy types.
        
        Returns:
            List of strategy types
        """
        return list(self._strategies.keys())
    
    def list_active_strategies(self) -> List[StrategyType]:
        """
        List all active (non-experimental) strategy types.
        
        Returns:
            List of strategy types
        """
        return [s for s, m in self._metadata.items() if not m.is_experimental]
    
    def get_supported_exchanges(self, strategy_type: StrategyType) -> List[str]:
        """
        Get exchanges supported by a strategy.
        
        Args:
            strategy_type: Strategy type
            
        Returns:
            List of exchange names
        """
        metadata = self._metadata.get(strategy_type)
        return metadata.supported_exchanges if metadata else []
    
    def find_strategy_for_exchange(
        self,
        exchange: str,
        prefer_active: bool = True,
    ) -> Optional[StrategyType]:
        """
        Find a strategy that supports an exchange.
        
        Args:
            exchange: Exchange name
            prefer_active: Prefer active (non-experimental) strategies
            
        Returns:
            StrategyType or None
        """
        candidates = []
        
        for strategy_type, metadata in self._metadata.items():
            if exchange in metadata.supported_exchanges or "all" in metadata.supported_exchanges:
                if prefer_active and metadata.is_experimental:
                    continue
                candidates.append((strategy_type, metadata.priority))
        
        if not candidates:
            return None
        
        # Sort by priority (lower is better)
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]
    
    def is_valid_strategy(self, strategy_type: StrategyType) -> bool:
        """
        Check if a strategy type is valid.
        
        Args:
            strategy_type: Strategy type
            
        Returns:
            True if valid
        """
        return strategy_type in self._strategies


class StrategyFactory:
    """
    Factory for creating strategy instances.
    
    Features:
    - Dynamic strategy creation
    - Configuration validation
    - Automatic dependency injection
    - Strategy caching
    - Instance management
    """
    
    _instance = None
    _strategy_instances: Dict[str, BaseStrategy] = {}
    
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
            self.registry = StrategyRegistry()
            self.logger.info("StrategyFactory initialized")
    
    @classmethod
    def create_strategy(
        cls,
        params: StrategyCreationParams,
    ) -> Optional[BaseStrategy]:
        """
        Create a strategy instance.
        
        Args:
            params: Strategy creation parameters
            
        Returns:
            Strategy instance or None
        """
        factory = cls._get_instance()
        return factory._create_strategy(params)
    
    @classmethod
    def create_strategy_from_config(
        cls,
        strategy_type: Union[str, StrategyType],
        exchanges: Dict[ExchangeType, BaseExchange],
        executor: BaseExecutor,
        config: Dict[str, Any],
    ) -> Optional[BaseStrategy]:
        """
        Create a strategy from configuration.
        
        Args:
            strategy_type: Strategy type
            exchanges: Dictionary of exchange instances
            executor: Execution engine
            config: Configuration dictionary
            
        Returns:
            Strategy instance or None
        """
        # Parse strategy type
        if isinstance(strategy_type, str):
            try:
                strategy_type = StrategyType(strategy_type.lower())
            except ValueError:
                # Try to find matching strategy type
                strategy_type = cls._find_matching_strategy(strategy_type)
                if not strategy_type:
                    return None
        
        # Build creation parameters
        params = StrategyCreationParams(
            strategy_type=strategy_type,
            exchanges=exchanges,
            executor=executor,
            config=config,
            min_profit_threshold=config.get("min_profit_threshold"),
            min_confidence=config.get("min_confidence"),
            extra_params=config.get("extra_params", {}),
        )
        
        return cls.create_strategy(params)
    
    @classmethod
    def get_strategy(
        cls,
        strategy_id: str,
    ) -> Optional[BaseStrategy]:
        """
        Get a cached strategy instance.
        
        Args:
            strategy_id: Strategy ID
            
        Returns:
            Strategy instance or None
        """
        factory = cls._get_instance()
        return factory._strategy_instances.get(strategy_id)
    
    @classmethod
    def register_strategy_instance(
        cls,
        strategy_id: str,
        strategy: BaseStrategy,
    ) -> None:
        """
        Register a strategy instance.
        
        Args:
            strategy_id: Strategy ID
            strategy: Strategy instance
        """
        factory = cls._get_instance()
        factory._strategy_instances[strategy_id] = strategy
        factory.logger.info(f"Registered strategy instance: {strategy_id}")
    
    @classmethod
    def remove_strategy_instance(cls, strategy_id: str) -> bool:
        """
        Remove a strategy instance.
        
        Args:
            strategy_id: Strategy ID
            
        Returns:
            True if removed
        """
        factory = cls._get_instance()
        if strategy_id in factory._strategy_instances:
            del factory._strategy_instances[strategy_id]
            factory.logger.info(f"Removed strategy instance: {strategy_id}")
            return True
        return False
    
    @classmethod
    def list_strategy_types(cls) -> List[StrategyType]:
        """
        List all available strategy types.
        
        Returns:
            List of strategy types
        """
        factory = cls._get_instance()
        return factory.registry.list_strategies()
    
    @classmethod
    def list_strategy_instances(cls) -> List[str]:
        """
        List all registered strategy instances.
        
        Returns:
            List of strategy IDs
        """
        factory = cls._get_instance()
        return list(factory._strategy_instances.keys())
    
    @classmethod
    def _get_instance(cls) -> "StrategyFactory":
        """Get or create factory instance."""
        if cls._instance is None:
            cls._instance = StrategyFactory()
        return cls._instance
    
    def _create_strategy(self, params: StrategyCreationParams) -> Optional[BaseStrategy]:
        """
        Internal method for creating a strategy.
        
        Args:
            params: Strategy creation parameters
            
        Returns:
            Strategy instance or None
        """
        try:
            # Get strategy class
            strategy_type = params.strategy_type
            if isinstance(strategy_type, str):
                try:
                    strategy_type = StrategyType(strategy_type.lower())
                except ValueError:
                    strategy_type = self._find_matching_strategy(strategy_type)
                    if not strategy_type:
                        self.logger.error(f"Unknown strategy type: {params.strategy_type}")
                        return None
            
            strategy_class = self.registry.get_strategy_class(strategy_type)
            if not strategy_class:
                self.logger.error(f"Strategy not found: {strategy_type}")
                return None
            
            metadata = self.registry.get_metadata(strategy_type)
            if not metadata:
                self.logger.error(f"Metadata not found for: {strategy_type}")
                return None
            
            # Create strategy based on type
            if strategy_type == StrategyType.MOMENTUM:
                return MomentumArbitrage(
                    exchanges=params.exchanges,
                    executor=params.executor,
                    min_momentum=params.extra_params.get("min_momentum", Decimal("0.02")),
                    max_momentum=params.extra_params.get("max_momentum", Decimal("0.15")),
                    min_correlation=params.extra_params.get("min_correlation", Decimal("0.6")),
                    min_profit=params.extra_params.get("min_profit", Decimal("0.001")),
                    max_lead_lag=params.extra_params.get("max_lead_lag", 10),
                    config=params.config,
                    logger=self.logger,
                )
            
            elif strategy_type == StrategyType.STATISTICAL:
                return StatisticalStrategy(
                    exchanges=params.exchanges,
                    executor=params.executor,
                    min_cointegration_pvalue=params.extra_params.get("min_cointegration_pvalue", Decimal("0.05")),
                    min_correlation=params.extra_params.get("min_correlation", Decimal("0.7")),
                    max_correlation=params.extra_params.get("max_correlation", Decimal("0.95")),
                    zscore_entry=params.extra_params.get("zscore_entry", Decimal("2.0")),
                    zscore_exit=params.extra_params.get("zscore_exit", Decimal("0.5")),
                    max_pairs=params.extra_params.get("max_pairs", 50),
                    config=params.config,
                    logger=self.logger,
                )
            
            # Add other strategy types here as they are implemented
            # elif strategy_type == StrategyType.DEX_ARBITRAGE:
            #     return DexArbitrage(...)
            # elif strategy_type == StrategyType.CROSS_EXCHANGE:
            #     return CrossExchangeStrategy(...)
            # etc.
            
            else:
                self.logger.error(f"Strategy type not yet implemented: {strategy_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Strategy creation failed: {e}")
            return None
    
    def _find_matching_strategy(
        self,
        strategy_type_str: str,
    ) -> Optional[StrategyType]:
        """Find matching strategy type from string."""
        strategy_type_str = strategy_type_str.lower()
        for strategy_type in self.registry.list_strategies():
            if strategy_type.value == strategy_type_str:
                return strategy_type
            if strategy_type_str in strategy_type.value:
                return strategy_type
            if strategy_type.name.lower() == strategy_type_str:
                return strategy_type
        return None


# Utility functions
def create_strategy(params: StrategyCreationParams) -> Optional[BaseStrategy]:
    """
    Create a strategy instance.
    
    Args:
        params: Strategy creation parameters
        
    Returns:
        Strategy instance or None
    """
    return StrategyFactory.create_strategy(params)


def create_strategy_from_config(
    strategy_type: Union[str, StrategyType],
    exchanges: Dict[ExchangeType, BaseExchange],
    executor: BaseExecutor,
    config: Dict[str, Any],
) -> Optional[BaseStrategy]:
    """
    Create a strategy from configuration.
    
    Args:
        strategy_type: Strategy type
        exchanges: Dictionary of exchange instances
        executor: Execution engine
        config: Configuration dictionary
        
    Returns:
        Strategy instance or None
    """
    return StrategyFactory.create_strategy_from_config(
        strategy_type, exchanges, executor, config
    )


def list_strategy_types() -> List[StrategyType]:
    """
    List all available strategy types.
    
    Returns:
        List of strategy types
    """
    return StrategyFactory.list_strategy_types()


def get_strategy(strategy_id: str) -> Optional[BaseStrategy]:
    """
    Get a cached strategy instance.
    
    Args:
        strategy_id: Strategy ID
        
    Returns:
        Strategy instance or None
    """
    return StrategyFactory.get_strategy(strategy_id)


def register_strategy_instance(strategy_id: str, strategy: BaseStrategy) -> None:
    """
    Register a strategy instance.
    
    Args:
        strategy_id: Strategy ID
        strategy: Strategy instance
    """
    StrategyFactory.register_strategy_instance(strategy_id, strategy)


def remove_strategy_instance(strategy_id: str) -> bool:
    """
    Remove a strategy instance.
    
    Args:
        strategy_id: Strategy ID
        
    Returns:
        True if removed
    """
    return StrategyFactory.remove_strategy_instance(strategy_id)


# Module exports
__all__ = [
    'StrategyFactory',
    'StrategyRegistry',
    'StrategyType',
    'StrategyMetadata',
    'StrategyCreationParams',
    'create_strategy',
    'create_strategy_from_config',
    'list_strategy_types',
    'get_strategy',
    'register_strategy_instance',
    'remove_strategy_instance',
]
