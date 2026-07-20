# trading/bots/arbitrage_bot/exchanges/exchange_factory.py
# NEXUS AI TRADING SYSTEM - FULL VERSION
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Author: Dr X... - Majority Shareholder

"""
NEXUS Exchange Factory - Advanced Exchange Management System
Version: 3.0.0 - FULL PRODUCTION READY
Description: Enterprise-grade exchange factory for dynamic instantiation,
management, and orchestration of multiple exchange connectors with
automatic configuration, health monitoring, and failover capabilities.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Type, Any, Union, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import importlib
from functools import lru_cache
import json
import os
import yaml

from trading.bots.arbitrage_bot.exchanges.base_exchange import BaseExchange
from trading.bots.arbitrage_bot.exchanges.binance import BinanceExchange, BinanceConfig
from trading.bots.arbitrage_bot.exchanges.bitget import BitgetExchange, BitgetConfig
from trading.bots.arbitrage_bot.exchanges.bybit import BybitExchange, BybitConfig
from trading.bots.arbitrage_bot.exchanges.coinbase import CoinbaseExchange, CoinbaseConfig
from trading.bots.arbitrage_bot.exchanges.curve import CurveExchange, CurveConfig
from trading.bots.arbitrage_bot.exchanges.dydx import DyDxExchange, DyDxConfig
from trading.bots.arbitrage_bot.exchanges.kraken import KrakenExchange, KrakenConfig
from trading.bots.arbitrage_bot.exchanges.kucoin import KuCoinExchange, KuCoinConfig
from trading.bots.arbitrage_bot.exchanges.okx import OKXExchange, OKXConfig
from trading.bots.arbitrage_bot.exchanges.uniswap import UniswapExchange, UniswapConfig
from trading.bots.arbitrage_bot.exchanges.pancakeswap import PancakeSwapExchange, PancakeSwapConfig
from trading.bots.arbitrage_bot.exchanges.oneinch import OneInchExchange, OneInchConfig
from trading.bots.arbitrage_bot.exchanges.ftx import FTXExchange, FTXConfig
from trading.bots.arbitrage_bot.exchanges.gateio import GateIOExchange, GateIOConfig
from trading.bots.arbitrage_bot.exchanges.huobi import HuobiExchange, HuobiConfig

from trading.bots.arbitrage_bot.exceptions import (
    ExchangeError, ConfigurationError, ExchangeNotFoundError,
    ExchangeConnectionError, ExchangeAuthenticationError
)

logger = logging.getLogger("nexus.arbitrage.exchange_factory")


class ExchangeType(Enum):
    """Supported exchange types."""
    # Centralized Exchanges (CEX)
    BINANCE = "binance"
    BITGET = "bitget"
    BYBIT = "bybit"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    KUCOIN = "kucoin"
    OKX = "okx"
    FTX = "ftx"
    GATEIO = "gateio"
    HUOBI = "huobi"
    
    # Decentralized Exchanges (DEX)
    CURVE = "curve"
    DYDX = "dydx"
    UNISWAP = "uniswap"
    PANCAKESWAP = "pancakeswap"
    ONEINCH = "oneinch"


class ExchangeMarket(Enum):
    """Market types for exchanges."""
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    OPTIONS = "options"
    MARGIN = "margin"
    LEVERAGED = "leveraged"


@dataclass
class ExchangeRegistryEntry:
    """Registry entry for an exchange."""
    exchange_type: ExchangeType
    exchange_class: Type[BaseExchange]
    config_class: Any
    markets: List[ExchangeMarket]
    default_config: Dict[str, Any]
    supported_chains: List[int] = field(default_factory=list)
    is_dex: bool = False
    is_cex: bool = True


@dataclass
class ExchangeConnectionPool:
    """Connection pool for exchange instances."""
    max_connections: int = 10
    timeout: float = 30.0
    health_check_interval: float = 60.0
    
    # Internal state
    _instances: Dict[str, BaseExchange] = field(default_factory=dict)
    _in_use: Set[str] = field(default_factory=set)
    _health_status: Dict[str, bool] = field(default_factory=dict)
    _last_check: Dict[str, float] = field(default_factory=dict)


@dataclass
class ExchangeFactoryConfig:
    """Configuration for the exchange factory."""
    enable_health_checks: bool = True
    enable_failover: bool = True
    enable_load_balancing: bool = True
    health_check_interval: float = 60.0
    connection_timeout: float = 30.0
    max_connections_per_exchange: int = 5
    auto_reconnect: bool = True
    cache_configs: bool = True
    config_cache_ttl: float = 300.0
    log_level: str = "INFO"


class ExchangeRegistry:
    """
    Registry for all available exchange implementations.
    Handles registration, discovery, and metadata management.
    """
    
    _instance = None
    _registry: Dict[ExchangeType, ExchangeRegistryEntry] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ExchangeRegistry, cls).__new__(cls)
            cls._instance._initialize_registry()
        return cls._instance
        
    def _initialize_registry(self) -> None:
        """Initialize the exchange registry with all supported exchanges."""
        self._registry = {
            # Centralized Exchanges
            ExchangeType.BINANCE: ExchangeRegistryEntry(
                exchange_type=ExchangeType.BINANCE,
                exchange_class=BinanceExchange,
                config_class=BinanceConfig,
                markets=[ExchangeMarket.SPOT, ExchangeMarket.FUTURES, ExchangeMarket.PERPETUAL],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_minute": 1200,
                    "enable_compression": True
                },
                is_cex=True,
                is_dex=False
            ),
            ExchangeType.BITGET: ExchangeRegistryEntry(
                exchange_type=ExchangeType.BITGET,
                exchange_class=BitgetExchange,
                config_class=BitgetConfig,
                markets=[ExchangeMarket.SPOT, ExchangeMarket.FUTURES, ExchangeMarket.PERPETUAL],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_second": 50,
                    "enable_compression": True
                },
                is_cex=True,
                is_dex=False
            ),
            ExchangeType.BYBIT: ExchangeRegistryEntry(
                exchange_type=ExchangeType.BYBIT,
                exchange_class=BybitExchange,
                config_class=BybitConfig,
                markets=[ExchangeMarket.SPOT, ExchangeMarket.FUTURES, ExchangeMarket.PERPETUAL, ExchangeMarket.OPTIONS],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_second": 50,
                    "enable_compression": True,
                    "market_type": "spot"
                },
                is_cex=True,
                is_dex=False
            ),
            ExchangeType.COINBASE: ExchangeRegistryEntry(
                exchange_type=ExchangeType.COINBASE,
                exchange_class=CoinbaseExchange,
                config_class=CoinbaseConfig,
                markets=[ExchangeMarket.SPOT],
                default_config={
                    "sandbox": False,
                    "request_timeout": 10.0,
                    "max_requests_per_second": 25,
                    "enable_compression": True
                },
                is_cex=True,
                is_dex=False
            ),
            ExchangeType.KRAKEN: ExchangeRegistryEntry(
                exchange_type=ExchangeType.KRAKEN,
                exchange_class=KrakenExchange,
                config_class=KrakenConfig,
                markets=[ExchangeMarket.SPOT, ExchangeMarket.FUTURES],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_minute": 600,
                    "enable_compression": True
                },
                is_cex=True,
                is_dex=False
            ),
            ExchangeType.KUCOIN: ExchangeRegistryEntry(
                exchange_type=ExchangeType.KUCOIN,
                exchange_class=KuCoinExchange,
                config_class=KuCoinConfig,
                markets=[ExchangeMarket.SPOT, ExchangeMarket.FUTURES, ExchangeMarket.MARGIN],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_second": 30,
                    "enable_compression": True
                },
                is_cex=True,
                is_dex=False
            ),
            ExchangeType.OKX: ExchangeRegistryEntry(
                exchange_type=ExchangeType.OKX,
                exchange_class=OKXExchange,
                config_class=OKXConfig,
                markets=[ExchangeMarket.SPOT, ExchangeMarket.FUTURES, ExchangeMarket.PERPETUAL, ExchangeMarket.OPTIONS],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_second": 60,
                    "enable_compression": True
                },
                is_cex=True,
                is_dex=False
            ),
            ExchangeType.FTX: ExchangeRegistryEntry(
                exchange_type=ExchangeType.FTX,
                exchange_class=FTXExchange,
                config_class=FTXConfig,
                markets=[ExchangeMarket.SPOT, ExchangeMarket.FUTURES, ExchangeMarket.PERPETUAL],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_minute": 600,
                    "enable_compression": True
                },
                is_cex=True,
                is_dex=False
            ),
            ExchangeType.GATEIO: ExchangeRegistryEntry(
                exchange_type=ExchangeType.GATEIO,
                exchange_class=GateIOExchange,
                config_class=GateIOConfig,
                markets=[ExchangeMarket.SPOT, ExchangeMarket.FUTURES, ExchangeMarket.PERPETUAL],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_second": 30,
                    "enable_compression": True
                },
                is_cex=True,
                is_dex=False
            ),
            ExchangeType.HUOBI: ExchangeRegistryEntry(
                exchange_type=ExchangeType.HUOBI,
                exchange_class=HuobiExchange,
                config_class=HuobiConfig,
                markets=[ExchangeMarket.SPOT, ExchangeMarket.FUTURES],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_second": 20,
                    "enable_compression": True
                },
                is_cex=True,
                is_dex=False
            ),
            
            # Decentralized Exchanges
            ExchangeType.CURVE: ExchangeRegistryEntry(
                exchange_type=ExchangeType.CURVE,
                exchange_class=CurveExchange,
                config_class=CurveConfig,
                markets=[ExchangeMarket.SPOT],
                default_config={
                    "web3_provider": "https://eth.llamarpc.com",
                    "chain_id": 1,
                    "request_timeout": 30.0,
                    "slippage_tolerance": 0.005
                },
                is_cex=False,
                is_dex=True,
                supported_chains=[1, 10, 137, 42161, 43114, 250, 56]
            ),
            ExchangeType.DYDX: ExchangeRegistryEntry(
                exchange_type=ExchangeType.DYDX,
                exchange_class=DyDxExchange,
                config_class=DyDxConfig,
                markets=[ExchangeMarket.PERPETUAL],
                default_config={
                    "testnet": False,
                    "request_timeout": 10.0,
                    "max_requests_per_second": 30,
                    "max_leverage": 25,
                    "enable_compression": True
                },
                is_cex=False,
                is_dex=True
            ),
            ExchangeType.UNISWAP: ExchangeRegistryEntry(
                exchange_type=ExchangeType.UNISWAP,
                exchange_class=UniswapExchange,
                config_class=UniswapConfig,
                markets=[ExchangeMarket.SPOT],
                default_config={
                    "web3_provider": "https://eth.llamarpc.com",
                    "chain_id": 1,
                    "slippage_tolerance": 0.01,
                    "router_address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
                },
                is_cex=False,
                is_dex=True,
                supported_chains=[1, 10, 137, 42161, 43114]
            ),
            ExchangeType.PANCAKESWAP: ExchangeRegistryEntry(
                exchange_type=ExchangeType.PANCAKESWAP,
                exchange_class=PancakeSwapExchange,
                config_class=PancakeSwapConfig,
                markets=[ExchangeMarket.SPOT],
                default_config={
                    "web3_provider": "https://bsc-dataseed.binance.org",
                    "chain_id": 56,
                    "slippage_tolerance": 0.01,
                    "router_address": "0x10ED43C718714eb63d5aA57B78B54704E256024E"
                },
                is_cex=False,
                is_dex=True,
                supported_chains=[56]
            ),
            ExchangeType.ONEINCH: ExchangeRegistryEntry(
                exchange_type=ExchangeType.ONEINCH,
                exchange_class=OneInchExchange,
                config_class=OneInchConfig,
                markets=[ExchangeMarket.SPOT],
                default_config={
                    "api_url": "https://api.1inch.io/v5.0",
                    "chain_id": 1,
                    "request_timeout": 10.0,
                    "slippage_tolerance": 0.01
                },
                is_cex=False,
                is_dex=True,
                supported_chains=[1, 10, 137, 42161, 43114, 56, 250]
            )
        }
        
    def get_exchange(self, exchange_type: ExchangeType) -> Optional[ExchangeRegistryEntry]:
        """Get exchange registry entry by type."""
        return self._registry.get(exchange_type)
        
    def get_all_exchanges(self) -> List[ExchangeRegistryEntry]:
        """Get all registered exchange entries."""
        return list(self._registry.values())
        
    def get_exchanges_by_type(self, is_cex: Optional[bool] = None, is_dex: Optional[bool] = None) -> List[ExchangeRegistryEntry]:
        """Get exchanges filtered by type (CEX/DEX)."""
        result = []
        for entry in self._registry.values():
            if is_cex is not None and entry.is_cex != is_cex:
                continue
            if is_dex is not None and entry.is_dex != is_dex:
                continue
            result.append(entry)
        return result
        
    def get_exchanges_by_market(self, market: ExchangeMarket) -> List[ExchangeRegistryEntry]:
        """Get exchanges that support a specific market type."""
        result = []
        for entry in self._registry.values():
            if market in entry.markets:
                result.append(entry)
        return result
        
    def get_exchanges_by_chain(self, chain_id: int) -> List[ExchangeRegistryEntry]:
        """Get exchanges that support a specific chain."""
        result = []
        for entry in self._registry.values():
            if chain_id in entry.supported_chains:
                result.append(entry)
        return result


class ExchangeFactory:
    """
    Enterprise-grade Exchange Factory for dynamic exchange management.
    
    Features:
    - Dynamic exchange instantiation
    - Connection pooling and reuse
    - Health checking and monitoring
    - Automatic failover
    - Load balancing across multiple exchange instances
    - Configuration management
    - Rate limiting coordination
    - Circuit breaker integration
    - Graceful degradation
    - Comprehensive logging and metrics
    """
    
    _instance = None
    
    def __new__(cls, config: Optional[ExchangeFactoryConfig] = None):
        if cls._instance is None:
            cls._instance = super(ExchangeFactory, cls).__new__(cls)
            cls._instance._initialize(config or ExchangeFactoryConfig())
        return cls._instance
        
    def _initialize(self, config: ExchangeFactoryConfig) -> None:
        """Initialize the exchange factory."""
        self.config = config
        self.registry = ExchangeRegistry()
        self._log = logger.getChild("exchange_factory")
        
        # Connection pools
        self._pools: Dict[str, ExchangeConnectionPool] = {}
        
        # Exchange instances
        self._instances: Dict[str, BaseExchange] = {}
        self._instance_configs: Dict[str, Any] = {}
        
        # Health status
        self._health_status: Dict[str, bool] = {}
        
        # Locks
        self._instance_lock = asyncio.Lock()
        self._pool_lock = asyncio.Lock()
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._shutdown_requested = False
        
        # Metrics
        self._metrics = {
            "instances_created": 0,
            "instances_active": 0,
            "connections_created": 0,
            "connections_active": 0,
            "health_checks": 0,
            "health_check_failures": 0,
            "failovers": 0,
            "load_balancing_events": 0
        }
        
        self._log.info("ExchangeFactory initialized (version=3.0.0)")
        
    def __repr__(self) -> str:
        return f"ExchangeFactory(instances={len(self._instances)}, pools={len(self._pools)})"
        
    # ======================== EXCHANGE CREATION ========================
    
    async def create_exchange(
        self,
        exchange_type: Union[ExchangeType, str],
        config: Optional[Dict[str, Any]] = None,
        instance_id: Optional[str] = None,
        reuse_existing: bool = True
    ) -> BaseExchange:
        """
        Create or retrieve an exchange instance.
        
        Args:
            exchange_type: Type of exchange to create
            config: Configuration for the exchange
            instance_id: Unique identifier for the instance
            reuse_existing: Whether to reuse existing instance
            
        Returns:
            Exchange instance
        """
        # Normalize exchange type
        if isinstance(exchange_type, str):
            exchange_type = ExchangeType(exchange_type.lower())
            
        # Get registry entry
        registry_entry = self.registry.get_exchange(exchange_type)
        if not registry_entry:
            raise ExchangeNotFoundError(f"Exchange type not found: {exchange_type}")
            
        # Generate instance ID
        if not instance_id:
            instance_id = f"{exchange_type.value}_{int(time.time())}"
            
        # Check if instance already exists
        if reuse_existing and instance_id in self._instances:
            self._log.debug(f"Reusing existing exchange instance: {instance_id}")
            return self._instances[instance_id]
            
        # Merge configuration
        merged_config = self._merge_config(
            registry_entry.default_config,
            config or {}
        )
        
        # Create config object
        config_obj = self._create_config_object(
            registry_entry.config_class,
            merged_config
        )
        
        # Create exchange instance
        try:
            exchange = registry_entry.exchange_class(config_obj)
            
            # Store instance
            async with self._instance_lock:
                self._instances[instance_id] = exchange
                self._instance_configs[instance_id] = merged_config
                self._metrics["instances_created"] += 1
                self._metrics["instances_active"] = len(self._instances)
                
            self._log.info(f"Created exchange instance: {instance_id} ({exchange_type.value})")
            return exchange
            
        except Exception as e:
            self._log.error(f"Failed to create exchange {instance_id}: {e}")
            raise ExchangeError(f"Exchange creation failed: {e}")
            
    def _merge_config(self, default_config: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge default and user configurations."""
        merged = default_config.copy()
        
        for key, value in user_config.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._merge_config(merged[key], value)
            else:
                merged[key] = value
                
        return merged
        
    def _create_config_object(self, config_class: Any, config_dict: Dict[str, Any]) -> Any:
        """Create a configuration object from a dictionary."""
        try:
            return config_class(**config_dict)
        except TypeError as e:
            self._log.warning(f"Config creation failed, using dict: {e}")
            return config_dict
            
    # ======================== CONNECTION MANAGEMENT ========================
    
    async def connect_exchange(
        self,
        exchange: Union[BaseExchange, str],
        retry: bool = True,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Connect an exchange instance.
        
        Args:
            exchange: Exchange instance or instance ID
            retry: Whether to retry on failure
            timeout: Connection timeout
            
        Returns:
            bool: True if connection successful
        """
        # Get exchange instance
        if isinstance(exchange, str):
            exchange = self.get_instance(exchange)
            if not exchange:
                raise ExchangeNotFoundError(f"Exchange instance not found: {exchange}")
                
        try:
            # Set timeout
            if timeout:
                return await asyncio.wait_for(
                    exchange.connect(retry=retry),
                    timeout=timeout
                )
            else:
                return await exchange.connect(retry=retry)
                
        except asyncio.TimeoutError:
            self._log.error(f"Connection timeout for {exchange}")
            raise ExchangeConnectionError(f"Connection timeout for {exchange}")
        except Exception as e:
            self._log.error(f"Connection failed for {exchange}: {e}")
            raise ExchangeConnectionError(f"Connection failed: {e}")
            
    async def disconnect_exchange(
        self,
        exchange: Union[BaseExchange, str],
        graceful: bool = True
    ) -> None:
        """
        Disconnect an exchange instance.
        
        Args:
            exchange: Exchange instance or instance ID
            graceful: Whether to perform graceful shutdown
        """
        if isinstance(exchange, str):
            exchange = self.get_instance(exchange)
            if not exchange:
                return
                
        try:
            await exchange.disconnect(graceful=graceful)
            self._log.info(f"Disconnected exchange: {exchange}")
        except Exception as e:
            self._log.warning(f"Disconnect error for {exchange}: {e}")
            
    async def reconnect_exchange(
        self,
        exchange: Union[BaseExchange, str],
        retry: bool = True
    ) -> bool:
        """
        Reconnect an exchange instance.
        
        Args:
            exchange: Exchange instance or instance ID
            retry: Whether to retry on failure
            
        Returns:
            bool: True if reconnection successful
        """
        await self.disconnect_exchange(exchange, graceful=True)
        return await self.connect_exchange(exchange, retry=retry)
        
    # ======================== INSTANCE MANAGEMENT ========================
    
    def get_instance(self, instance_id: str) -> Optional[BaseExchange]:
        """Get an exchange instance by ID."""
        return self._instances.get(instance_id)
        
    def get_all_instances(self) -> Dict[str, BaseExchange]:
        """Get all exchange instances."""
        return self._instances.copy()
        
    def get_instances_by_type(self, exchange_type: ExchangeType) -> List[BaseExchange]:
        """Get all instances of a specific type."""
        result = []
        for instance_id, exchange in self._instances.items():
            if isinstance(exchange, self.registry.get_exchange(exchange_type).exchange_class):
                result.append(exchange)
        return result
        
    async def remove_instance(self, instance_id: str, force: bool = False) -> bool:
        """
        Remove an exchange instance.
        
        Args:
            instance_id: Instance ID
            force: Force removal even if connected
            
        Returns:
            bool: True if removed successfully
        """
        async with self._instance_lock:
            if instance_id not in self._instances:
                return False
                
            exchange = self._instances[instance_id]
            
            if not force and exchange._is_connected:
                raise ExchangeError(f"Instance {instance_id} is still connected")
                
            if exchange._is_connected:
                await self.disconnect_exchange(exchange)
                
            del self._instances[instance_id]
            self._instance_configs.pop(instance_id, None)
            self._metrics["instances_active"] = len(self._instances)
            
            self._log.info(f"Removed exchange instance: {instance_id}")
            return True
            
    # ======================== HEALTH CHECKING ========================
    
    async def health_check(self, instance_id: str) -> Dict[str, Any]:
        """
        Perform health check on an exchange instance.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            Health check results
        """
        exchange = self.get_instance(instance_id)
        if not exchange:
            return {
                "status": "unhealthy",
                "error": f"Instance {instance_id} not found",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        try:
            result = await exchange.health_check(detailed=True)
            self._health_status[instance_id] = result["status"] == "healthy"
            self._metrics["health_checks"] += 1
            
            if not self._health_status[instance_id]:
                self._metrics["health_check_failures"] += 1
                
            return result
            
        except Exception as e:
            self._health_status[instance_id] = False
            self._metrics["health_check_failures"] += 1
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Perform health checks on all exchange instances.
        
        Returns:
            Dict of instance_id -> health check results
        """
        results = {}
        for instance_id in list(self._instances.keys()):
            results[instance_id] = await self.health_check(instance_id)
        return results
        
    # ======================== FAILOVER MANAGEMENT ========================
    
    async def get_failover_instance(
        self,
        exchange_type: ExchangeType,
        primary_instance_id: Optional[str] = None
    ) -> Optional[BaseExchange]:
        """
        Get a failover instance for a given exchange type.
        
        Args:
            exchange_type: Exchange type
            primary_instance_id: Primary instance ID (to exclude)
            
        Returns:
            Failover exchange instance or None
        """
        # Get all instances of this type
        instances = self.get_instances_by_type(exchange_type)
        
        # Filter out primary
        if primary_instance_id:
            instances = [i for i in instances if i._instance_id != primary_instance_id]
            
        # Find a healthy instance
        for instance in instances:
            instance_id = getattr(instance, "_instance_id", None)
            if instance_id and self._health_status.get(instance_id, False):
                self._metrics["failovers"] += 1
                self._log.info(f"Failover to instance {instance_id}")
                return instance
                
        # Create a new instance if none available
        try:
            new_instance = await self.create_exchange(exchange_type)
            await self.connect_exchange(new_instance)
            self._metrics["failovers"] += 1
            self._log.info(f"Created new failover instance: {new_instance}")
            return new_instance
        except Exception as e:
            self._log.error(f"Failover creation failed: {e}")
            return None
            
    # ======================== LOAD BALANCING ========================
    
    async def get_least_loaded_instance(
        self,
        exchange_type: ExchangeType
    ) -> Optional[BaseExchange]:
        """
        Get the least loaded instance of a given exchange type.
        
        Args:
            exchange_type: Exchange type
            
        Returns:
            Least loaded exchange instance or None
        """
        instances = self.get_instances_by_type(exchange_type)
        
        if not instances:
            return None
            
        # Calculate load based on active orders and connections
        min_load = float("inf")
        selected = None
        
        for instance in instances:
            if not self._health_status.get(getattr(instance, "_instance_id", ""), True):
                continue
                
            # Get load metrics
            try:
                metrics = instance.get_metrics()
                load = (
                    metrics.get("open_orders", 0) * 2 +
                    metrics.get("ws_connections", 0) * 1.5 +
                    metrics.get("requests_total", 0) / 1000
                )
                
                if load < min_load:
                    min_load = load
                    selected = instance
            except Exception:
                continue
                
        if selected:
            self._metrics["load_balancing_events"] += 1
            self._log.debug(f"Selected least loaded instance: {getattr(selected, '_instance_id', 'unknown')}")
            
        return selected
        
    # ======================== BULK OPERATIONS ========================
    
    async def connect_all(self, retry: bool = True) -> Dict[str, bool]:
        """
        Connect all exchange instances.
        
        Args:
            retry: Whether to retry on failure
            
        Returns:
            Dict of instance_id -> connection status
        """
        results = {}
        for instance_id, exchange in self._instances.items():
            try:
                results[instance_id] = await self.connect_exchange(exchange, retry=retry)
            except Exception as e:
                results[instance_id] = False
                self._log.error(f"Failed to connect {instance_id}: {e}")
        return results
        
    async def disconnect_all(self, graceful: bool = True) -> None:
        """Disconnect all exchange instances."""
        for instance_id in list(self._instances.keys()):
            await self.disconnect_exchange(instance_id, graceful=graceful)
            
    async def health_check_loop(self) -> None:
        """Periodic health check loop."""
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                if self.config.enable_health_checks:
                    await self.health_check_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error(f"Health check loop error: {e}")
                
    # ======================== CONFIGURATION MANAGEMENT ========================
    
    def load_config_from_file(self, file_path: str) -> Dict[str, Any]:
        """Load configuration from a file."""
        if not os.path.exists(file_path):
            raise ConfigurationError(f"Config file not found: {file_path}")
            
        with open(file_path, 'r') as f:
            if file_path.endswith('.json'):
                return json.load(f)
            elif file_path.endswith(('.yaml', '.yml')):
                return yaml.safe_load(f)
            else:
                raise ConfigurationError(f"Unsupported config file format: {file_path}")
                
    def load_config_from_env(self, prefix: str = "NEXUS_") -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                config[config_key] = value
        return config
        
    def save_config_to_file(
        self,
        config: Dict[str, Any],
        file_path: str,
        overwrite: bool = False
    ) -> None:
        """Save configuration to a file."""
        if os.path.exists(file_path) and not overwrite:
            raise ConfigurationError(f"Config file already exists: {file_path}")
            
        with open(file_path, 'w') as f:
            if file_path.endswith('.json'):
                json.dump(config, f, indent=2)
            elif file_path.endswith(('.yaml', '.yml')):
                yaml.dump(config, f, default_flow_style=False)
            else:
                raise ConfigurationError(f"Unsupported config file format: {file_path}")
                
    # ======================== METRICS ========================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get factory metrics."""
        return {
            **self._metrics,
            "instances": {
                instance_id: {
                    "type": type(exchange).__name__,
                    "connected": exchange._is_connected if hasattr(exchange, "_is_connected") else False,
                    "authenticated": exchange._is_authenticated if hasattr(exchange, "_is_authenticated") else False
                }
                for instance_id, exchange in self._instances.items()
            },
            "health_status": self._health_status
        }
        
    def reset_metrics(self) -> None:
        """Reset metrics."""
        self._metrics = {
            "instances_created": 0,
            "instances_active": 0,
            "connections_created": 0,
            "connections_active": 0,
            "health_checks": 0,
            "health_check_failures": 0,
            "failovers": 0,
            "load_balancing_events": 0
        }
        
    # ======================== SHUTDOWN ========================
    
    async def shutdown(self, graceful: bool = True) -> None:
        """Shutdown the exchange factory."""
        self._log.info("Shutting down ExchangeFactory...")
        self._shutdown_requested = True
        
        # Cancel background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        # Disconnect all instances
        await self.disconnect_all(graceful=graceful)
        
        # Clear instances
        async with self._instance_lock:
            self._instances.clear()
            self._instance_configs.clear()
            self._health_status.clear()
            
        self._log.info("ExchangeFactory shutdown complete")
        
    # ======================== CONTEXT MANAGER ========================
    
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()
        
    def __del__(self):
        if self._instances:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.shutdown())
                else:
                    asyncio.run(self.shutdown())
            except Exception:
                pass


# ======================== SINGLETON INSTANCE ========================

_global_factory: Optional[ExchangeFactory] = None


def get_exchange_factory(config: Optional[ExchangeFactoryConfig] = None) -> ExchangeFactory:
    """
    Get the global exchange factory instance.
    
    Args:
        config: Factory configuration
        
    Returns:
        ExchangeFactory instance
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = ExchangeFactory(config)
    return _global_factory


def reset_exchange_factory() -> None:
    """Reset the global exchange factory instance."""
    global _global_factory
    if _global_factory:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_factory.shutdown())
            else:
                asyncio.run(_global_factory.shutdown())
        except Exception:
            pass
    _global_factory = None


# ======================== HELPER FUNCTIONS ========================

async def create_quick_exchange(
    exchange_type: Union[ExchangeType, str],
    api_key: str,
    api_secret: str,
    **kwargs
) -> BaseExchange:
    """
    Quick create and connect an exchange.
    
    Args:
        exchange_type: Exchange type
        api_key: API key
        api_secret: API secret
        **kwargs: Additional configuration
        
    Returns:
        Connected exchange instance
    """
    config = {
        "api_key": api_key,
        "api_secret": api_secret,
        **kwargs
    }
    
    factory = get_exchange_factory()
    exchange = await factory.create_exchange(exchange_type, config)
    await factory.connect_exchange(exchange)
    return exchange


async def create_quick_dex_exchange(
    exchange_type: Union[ExchangeType, str],
    private_key: str,
    wallet_address: str,
    chain_id: int = 1,
    **kwargs
) -> BaseExchange:
    """
    Quick create and connect a DEX exchange.
    
    Args:
        exchange_type: Exchange type
        private_key: Wallet private key
        wallet_address: Wallet address
        chain_id: Chain ID
        **kwargs: Additional configuration
        
    Returns:
        Connected exchange instance
    """
    config = {
        "private_key": private_key,
        "wallet_address": wallet_address,
        "chain_id": chain_id,
        **kwargs
    }
    
    factory = get_exchange_factory()
    exchange = await factory.create_exchange(exchange_type, config)
    await factory.connect_exchange(exchange)
    return exchange


def get_supported_exchanges() -> List[str]:
    """
    Get list of all supported exchange names.
    
    Returns:
        List of exchange names
    """
    registry = ExchangeRegistry()
    return [e.exchange_type.value for e in registry.get_all_exchanges()]


def get_supported_exchanges_by_market(market: str) -> List[str]:
    """
    Get exchanges that support a specific market.
    
    Args:
        market: Market type (spot, futures, perpetual, options, margin)
        
    Returns:
        List of exchange names
    """
    registry = ExchangeRegistry()
    market_enum = ExchangeMarket(market.upper())
    return [e.exchange_type.value for e in registry.get_exchanges_by_market(market_enum)]
