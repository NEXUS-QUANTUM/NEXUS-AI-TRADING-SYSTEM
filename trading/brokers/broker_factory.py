# trading/brokers/broker_factory.py
"""
NEXUS AI TRADING SYSTEM - Broker Factory
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides the broker factory implementation for creating
broker instances dynamically based on configuration. It supports
automatic registration of broker implementations and provides
a centralized way to instantiate brokers.

The factory pattern allows the system to:
- Dynamically load broker implementations
- Switch between brokers at runtime
- Support multiple broker instances
- Maintain consistency across broker implementations
"""

import importlib
import importlib.util
import inspect
import os
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union, Callable, Awaitable
from dataclasses import dataclass, field

import aiohttp

from shared.utilities.logger import get_logger
from .base import (
    BaseBroker,
    BrokerConfig,
    BrokerName,
    BrokerException,
    PaperBroker,
    WebhookBroker,
    BrokerConfigComplete,
)
from .broker_config import BrokerConfigLoader

logger = get_logger(__name__)


# ============================================================================
# BROKER REGISTRY
# ============================================================================

class BrokerRegistry:
    """
    Registry for broker implementations.
    
    Manages the registration and discovery of broker implementations.
    Supports dynamic loading of broker modules and automatic registration
    of broker classes.
    """
    
    def __init__(self):
        """Initialize the broker registry."""
        self._broker_classes: Dict[BrokerName, Type[BaseBroker]] = {}
        self._broker_aliases: Dict[str, BrokerName] = {}
        self._broker_metadata: Dict[BrokerName, Dict[str, Any]] = {}
        self._initialized = False
        self.logger = logger
        
        # Register built-in brokers
        self._register_builtin_brokers()
    
    def _register_builtin_brokers(self) -> None:
        """Register built-in broker implementations."""
        # Paper and Webhook brokers are special cases
        self.register(
            BrokerName.PAPER,
            PaperBroker,
            metadata={
                "description": "Paper trading broker for simulation",
                "supports_websocket": False,
                "supports_market_data": False,
                "requires_authentication": False,
                "is_sandbox_only": True,
                "is_builtin": True,
            }
        )
        
        self.register(
            BrokerName.WEBHOOK,
            WebhookBroker,
            metadata={
                "description": "Webhook-based broker for external signals",
                "supports_websocket": False,
                "supports_market_data": False,
                "requires_authentication": False,
                "is_sandbox_only": False,
                "is_builtin": True,
            }
        )
        
        # Try to discover additional brokers
        self.discover_brokers()
    
    def register(
        self,
        broker_name: BrokerName,
        broker_class: Type[BaseBroker],
        alias: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a broker implementation.
        
        Args:
            broker_name: Name of the broker
            broker_class: Broker class (must inherit from BaseBroker)
            alias: Optional alias for the broker
            metadata: Optional metadata about the broker
        """
        if not issubclass(broker_class, BaseBroker):
            raise ValueError(
                f"Broker class {broker_class.__name__} must inherit from BaseBroker"
            )
        
        self._broker_classes[broker_name] = broker_class
        
        if alias:
            self._broker_aliases[alias.lower()] = broker_name
        
        if metadata:
            self._broker_metadata[broker_name] = metadata
        else:
            self._broker_metadata.setdefault(broker_name, {})
        
        self.logger.debug(f"Registered broker: {broker_name.value} -> {broker_class.__name__}")
    
    def get(self, broker_name: BrokerName) -> Optional[Type[BaseBroker]]:
        """
        Get a broker class by name.
        
        Args:
            broker_name: Name of the broker
            
        Returns:
            Optional[Type[BaseBroker]]: Broker class or None if not found
        """
        return self._broker_classes.get(broker_name)
    
    def get_by_alias(self, alias: str) -> Optional[BrokerName]:
        """
        Get a broker name by alias.
        
        Args:
            alias: Broker alias
            
        Returns:
            Optional[BrokerName]: Broker name or None if not found
        """
        return self._broker_aliases.get(alias.lower())
    
    def get_metadata(self, broker_name: BrokerName) -> Dict[str, Any]:
        """
        Get metadata for a broker.
        
        Args:
            broker_name: Name of the broker
            
        Returns:
            Dict: Broker metadata
        """
        return self._broker_metadata.get(broker_name, {})
    
    def list_brokers(self) -> List[BrokerName]:
        """
        List all registered brokers.
        
        Returns:
            List[BrokerName]: List of registered broker names
        """
        return list(self._broker_classes.keys())
    
    def is_registered(self, broker_name: BrokerName) -> bool:
        """
        Check if a broker is registered.
        
        Args:
            broker_name: Name of the broker
            
        Returns:
            bool: True if broker is registered
        """
        return broker_name in self._broker_classes
    
    def discover_brokers(self, directory: Optional[Path] = None) -> int:
        """
        Discover and register brokers from a directory.
        
        Scans Python files in the given directory and attempts to
        find and register broker implementations.
        
        Args:
            directory: Directory to scan (defaults to current directory)
            
        Returns:
            int: Number of brokers discovered
        """
        if directory is None:
            directory = Path(__file__).parent
        
        discovered = 0
        
        # Files to skip
        skip_files = [
            "__init__.py",
            "base.py",
            "broker_config.py",
            "broker_connection.py",
            "broker_factory.py",
        ]
        
        for file_path in directory.glob("*.py"):
            if file_path.name in skip_files:
                continue
            
            if file_path.name.startswith("__"):
                continue
            
            try:
                # Try to import the module
                module_name = file_path.stem
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    continue
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Look for broker classes in the module
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, BaseBroker)
                        and obj not in (BaseBroker, PaperBroker, WebhookBroker)
                        and obj.__module__ == module_name
                    ):
                        # Try to determine broker name from class name
                        class_name = obj.__name__.lower()
                        if "paper" in class_name or "webhook" in class_name:
                            continue
                        
                        # Try to map to BrokerName enum
                        try:
                            # Remove "broker" suffix if present
                            broker_name_str = class_name.replace("_broker", "").replace("broker", "")
                            broker_name = BrokerName(broker_name_str.strip())
                            self.register(broker_name, obj)
                            discovered += 1
                            self.logger.info(f"Discovered broker: {broker_name.value} from {file_path.name}")
                        except ValueError:
                            # If no direct match, try common patterns
                            broker_mapping = {
                                "binance": BrokerName.BINANCE,
                                "bybit": BrokerName.BYBIT,
                                "coinbase": BrokerName.COINBASE,
                                "kraken": BrokerName.KRAKEN,
                                "alpaca": BrokerName.ALPACA,
                                "oanda": BrokerName.OANDA,
                                "ibkr": BrokerName.IBKR,
                                "interactive_brokers": BrokerName.INTERACTIVE_BROKERS,
                                "tradier": BrokerName.TRADIER,
                                "tradestation": BrokerName.TRADESTATION,
                                "schwab": BrokerName.SCHWAB,
                                "fidelity": BrokerName.FIDELITY,
                                "etoro": BrokerName.ETORO,
                                "binance_us": BrokerName.BINANCE_US,
                                "ftx": BrokerName.FTX,
                                "kucoin": BrokerName.KUCOIN,
                            }
                            
                            # Try to find mapping
                            key = class_name.replace("_", "").replace("broker", "")
                            found = False
                            for pattern, mapped_name in broker_mapping.items():
                                if pattern in key:
                                    self.register(mapped_name, obj)
                                    discovered += 1
                                    found = True
                                    self.logger.info(f"Discovered broker: {mapped_name.value} from {file_path.name} (mapped from {key})")
                                    break
                            
                            if not found:
                                self.logger.debug(f"Could not map broker class: {class_name} from {file_path.name}")
                            
            except Exception as e:
                self.logger.warning(f"Failed to discover broker in {file_path.name}: {e}")
        
        return discovered
    
    def clear(self) -> None:
        """Clear all registered brokers (except built-in)."""
        # Keep built-in brokers
        builtin = [BrokerName.PAPER, BrokerName.WEBHOOK]
        self._broker_classes = {
            name: cls for name, cls in self._broker_classes.items()
            if name in builtin
        }
        self._broker_metadata = {
            name: meta for name, meta in self._broker_metadata.items()
            if name in builtin
        }
        self._broker_aliases = {}
        self.logger.info("Cleared broker registry (kept built-in brokers)")


# ============================================================================
# BROKER INSTANCE CACHE
# ============================================================================

@dataclass
class CachedBroker:
    """Cached broker instance with metadata"""
    broker: BaseBroker
    config: BrokerConfig
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    usage_count: int = 0
    connection_id: str = ""


class BrokerInstanceCache:
    """
    Cache for broker instances.
    
    Manages broker instance lifecycle including creation, caching,
    reuse, and cleanup of broker instances.
    """
    
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Initialize the broker instance cache.
        
        Args:
            max_size: Maximum number of cached instances
            ttl: Time-to-live for cached instances in seconds
        """
        self._cache: Dict[str, CachedBroker] = {}
        self._max_size = max_size
        self._ttl = ttl
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self.logger = logger
    
    async def get_or_create(
        self,
        key: str,
        factory: Callable[[], Awaitable[BaseBroker]],
        config: BrokerConfig,
    ) -> BaseBroker:
        """
        Get a cached broker instance or create a new one.
        
        Args:
            key: Cache key for the instance
            factory: Async factory function to create the broker
            config: Broker configuration
            
        Returns:
            BaseBroker: Broker instance
        """
        async with self._lock:
            # Check if instance exists and is valid
            if key in self._cache:
                cached = self._cache[key]
                
                # Check TTL
                if time.time() - cached.created_at > self._ttl:
                    # Expired, close and remove
                    await self._close_instance(key)
                else:
                    # Update usage
                    cached.last_used = time.time()
                    cached.usage_count += 1
                    return cached.broker
            
            # Create new instance
            broker = await factory()
            
            # Cache the instance
            cached = CachedBroker(
                broker=broker,
                config=config,
                connection_id=getattr(broker, "connection_id", ""),
            )
            self._cache[key] = cached
            
            # Clean up if cache is too large
            if len(self._cache) > self._max_size:
                await self._evict_oldest()
            
            # Start cleanup task if not running
            if not self._running:
                self._running = True
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            return broker
    
    async def _close_instance(self, key: str) -> None:
        """
        Close and remove a cached instance.
        
        Args:
            key: Cache key
        """
        if key in self._cache:
            cached = self._cache[key]
            try:
                await cached.broker.disconnect()
                if hasattr(cached.broker, "session") and cached.broker.session:
                    await cached.broker.session.close()
            except Exception as e:
                self.logger.error(f"Error closing cached broker {key}: {e}")
            finally:
                del self._cache[key]
                self.logger.debug(f"Removed cached broker: {key}")
    
    async def _evict_oldest(self) -> None:
        """Evict the oldest cached instance."""
        if not self._cache:
            return
        
        # Find oldest (least recently used)
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_used)
        await self._close_instance(oldest_key)
        self.logger.debug(f"Evicted oldest cached broker: {oldest_key}")
    
    async def _cleanup_loop(self) -> None:
        """Cleanup loop for expired instances."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                if not self._running:
                    break
                
                now = time.time()
                expired_keys = [
                    key for key, cached in self._cache.items()
                    if now - cached.created_at > self._ttl
                ]
                
                for key in expired_keys:
                    await self._close_instance(key)
                    self.logger.debug(f"Removed expired broker: {key}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
        
        self._running = False
    
    async def clear(self) -> None:
        """Clear all cached instances."""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        keys = list(self._cache.keys())
        for key in keys:
            await self._close_instance(key)
        
        self.logger.info("Cleared broker instance cache")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict: Cache statistics
        """
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl": self._ttl,
            "is_running": self._running,
            "instances": [
                {
                    "key": key,
                    "broker": cached.broker.name.value if cached.broker.name else "unknown",
                    "connection_id": cached.connection_id,
                    "usage_count": cached.usage_count,
                    "created_at": cached.created_at,
                    "last_used": cached.last_used,
                    "age": time.time() - cached.created_at,
                }
                for key, cached in self._cache.items()
            ],
        }


# ============================================================================
# BROKER FACTORY
# ============================================================================

class BrokerFactory:
    """
    Factory for creating broker instances.
    
    Provides a centralized way to create broker instances with:
    - Automatic broker registration and discovery
    - Instance caching for performance
    - Configuration validation
    - Support for both sync and async creation
    """
    
    _registry: Optional[BrokerRegistry] = None
    _cache: Optional[BrokerInstanceCache] = None
    _loader: Optional[BrokerConfigLoader] = None
    _initialized = False
    
    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure the factory is initialized."""
        if cls._initialized:
            return
        
        cls._registry = BrokerRegistry()
        cls._cache = BrokerInstanceCache()
        cls._loader = BrokerConfigLoader()
        
        # Load configurations
        cls._loader.load_all()
        
        cls._initialized = True
        logger.info("BrokerFactory initialized")
    
    @classmethod
    def initialize(cls, config_dir: Optional[Path] = None, auto_discover: bool = True) -> None:
        """
        Initialize the broker factory.
        
        Args:
            config_dir: Directory for broker configurations
            auto_discover: Whether to auto-discover broker implementations
        """
        if cls._initialized:
            return
        
        cls._registry = BrokerRegistry()
        cls._cache = BrokerInstanceCache()
        cls._loader = BrokerConfigLoader(config_dir)
        
        if auto_discover:
            # Already discovered in registry initialization
            pass
        
        # Load configurations
        cls._loader.load_all()
        
        cls._initialized = True
        logger.info("BrokerFactory initialized")
    
    @classmethod
    def register_broker(
        cls,
        broker_name: BrokerName,
        broker_class: Type[BaseBroker],
        alias: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a broker implementation.
        
        Args:
            broker_name: Name of the broker
            broker_class: Broker class
            alias: Optional alias
            metadata: Optional metadata
        """
        cls._ensure_initialized()
        cls._registry.register(broker_name, broker_class, alias, metadata)
    
    @classmethod
    def get_broker_class(cls, broker_name: BrokerName) -> Optional[Type[BaseBroker]]:
        """
        Get a broker class by name.
        
        Args:
            broker_name: Name of the broker
            
        Returns:
            Optional[Type[BaseBroker]]: Broker class or None
        """
        cls._ensure_initialized()
        return cls._registry.get(broker_name)
    
    @classmethod
    def get_broker_by_alias(cls, alias: str) -> Optional[BrokerName]:
        """
        Get a broker name by alias.
        
        Args:
            alias: Broker alias
            
        Returns:
            Optional[BrokerName]: Broker name or None
        """
        cls._ensure_initialized()
        return cls._registry.get_by_alias(alias)
    
    @classmethod
    def create_broker(
        cls,
        config: Union[BrokerConfig, BrokerConfigComplete, Dict[str, Any], str],
        session: Optional[aiohttp.ClientSession] = None,
        use_cache: bool = True,
    ) -> BaseBroker:
        """
        Create a broker instance (synchronous).
        
        Args:
            config: Broker configuration (config object, dict, or config ID)
            session: Optional aiohttp session
            use_cache: Whether to use the instance cache
            
        Returns:
            BaseBroker: Broker instance
            
        Raises:
            ValueError: If configuration is invalid
            BrokerException: If broker creation fails
        """
        cls._ensure_initialized()
        
        # Parse configuration
        broker_config = cls._parse_config(config)
        
        # Get broker class
        broker_class = cls._registry.get(broker_config.broker_name)
        if not broker_class:
            raise ValueError(
                f"Broker {broker_config.broker_name.value} not registered. "
                f"Available: {[b.value for b in cls._registry.list_brokers()]}"
            )
        
        # Create instance
        try:
            broker = broker_class(broker_config, session)
            return broker
        except Exception as e:
            raise BrokerException(f"Failed to create broker: {str(e)}")
    
    @classmethod
    async def create_broker_async(
        cls,
        config: Union[BrokerConfig, BrokerConfigComplete, Dict[str, Any], str],
        session: Optional[aiohttp.ClientSession] = None,
        use_cache: bool = True,
    ) -> BaseBroker:
        """
        Create a broker instance (asynchronous).
        
        Args:
            config: Broker configuration (config object, dict, or config ID)
            session: Optional aiohttp session
            use_cache: Whether to use the instance cache
            
        Returns:
            BaseBroker: Broker instance
            
        Raises:
            ValueError: If configuration is invalid
            BrokerException: If broker creation fails
        """
        cls._ensure_initialized()
        
        # Parse configuration
        broker_config = cls._parse_config(config)
        
        # Get broker class
        broker_class = cls._registry.get(broker_config.broker_name)
        if not broker_class:
            raise ValueError(
                f"Broker {broker_config.broker_name.value} not registered. "
                f"Available: {[b.value for b in cls._registry.list_brokers()]}"
            )
        
        # Generate cache key
        cache_key = (
            f"{broker_config.broker_name.value}"
            f"_{broker_config.sandbox_mode}"
            f"_{broker_config.account_type.value}"
        )
        
        if use_cache:
            # Create factory function
            async def create_broker() -> BaseBroker:
                return broker_class(broker_config, session)
            
            # Get from cache or create
            return await cls._cache.get_or_create(cache_key, create_broker, broker_config)
        
        # Create instance directly
        try:
            broker = broker_class(broker_config, session)
            return broker
        except Exception as e:
            raise BrokerException(f"Failed to create broker: {str(e)}")
    
    @classmethod
    def _parse_config(
        cls,
        config: Union[BrokerConfig, BrokerConfigComplete, Dict[str, Any], str],
    ) -> BrokerConfig:
        """
        Parse various configuration formats into BrokerConfig.
        
        Args:
            config: Configuration in various formats
            
        Returns:
            BrokerConfig: Parsed configuration
        """
        if isinstance(config, BrokerConfig):
            return config
        
        if isinstance(config, BrokerConfigComplete):
            return config.to_broker_config()
        
        if isinstance(config, dict):
            # Try to create BrokerConfig from dict
            try:
                return BrokerConfig(**config)
            except Exception as e:
                raise ValueError(f"Invalid config dict: {e}")
        
        if isinstance(config, str):
            # Try as broker name
            try:
                broker_name = BrokerName(config.lower())
                # Create default config
                complete = cls._loader.create_default_config(broker_name)
                return complete.to_broker_config()
            except ValueError:
                pass
            
            # Try as config ID
            loaded = cls._loader.get_config(config)
            if loaded:
                return loaded.to_broker_config()
            
            raise ValueError(f"Could not load configuration for: {config}")
        
        raise ValueError(f"Invalid configuration type: {type(config)}")
    
    @classmethod
    def get_config_loader(cls) -> BrokerConfigLoader:
        """
        Get the configuration loader instance.
        
        Returns:
            BrokerConfigLoader: Configuration loader
        """
        cls._ensure_initialized()
        return cls._loader
    
    @classmethod
    def get_registry(cls) -> BrokerRegistry:
        """
        Get the broker registry instance.
        
        Returns:
            BrokerRegistry: Broker registry
        """
        cls._ensure_initialized()
        return cls._registry
    
    @classmethod
    def get_cache(cls) -> BrokerInstanceCache:
        """
        Get the broker instance cache.
        
        Returns:
            BrokerInstanceCache: Instance cache
        """
        cls._ensure_initialized()
        return cls._cache
    
    @classmethod
    async def clear_cache(cls) -> None:
        """Clear the broker instance cache."""
        cls._ensure_initialized()
        await cls._cache.clear()
    
    @classmethod
    def list_available_brokers(cls) -> List[Dict[str, Any]]:
        """
        List all available brokers with metadata.
        
        Returns:
            List[Dict]: List of broker information
        """
        cls._ensure_initialized()
        
        brokers = []
        
        # Registered brokers
        for broker_name in cls._registry.list_brokers():
            meta = cls._registry.get_metadata(broker_name)
            brokers.append({
                "type": "registered",
                "name": broker_name.value,
                "registered": True,
                "metadata": meta,
            })
        
        # Configured brokers
        for config_id, config in cls._loader.configs.items():
            if config.enabled:
                brokers.append({
                    "type": "configured",
                    "name": config.name.value,
                    "id": config_id,
                    "environment": config.environment.value,
                    "account_type": config.account_type.value,
                    "sandbox": config.sandbox_mode,
                    "enabled": config.enabled,
                    "priority": config.priority,
                })
        
        return brokers
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict: Cache statistics
        """
        cls._ensure_initialized()
        return cls._cache.get_stats()
    
    @classmethod
    async def close_all(cls) -> None:
        """Close all broker instances and clean up."""
        if cls._cache:
            await cls._cache.clear()
        
        cls._initialized = False
        logger.info("BrokerFactory closed")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_broker(
    config: Union[BrokerConfig, BrokerConfigComplete, Dict[str, Any], str],
    session: Optional[aiohttp.ClientSession] = None,
) -> BaseBroker:
    """
    Create a broker instance (synchronous convenience function).
    
    Args:
        config: Broker configuration
        session: Optional aiohttp session
        
    Returns:
        BaseBroker: Broker instance
    """
    return BrokerFactory.create_broker(config, session)


async def create_broker_async(
    config: Union[BrokerConfig, BrokerConfigComplete, Dict[str, Any], str],
    session: Optional[aiohttp.ClientSession] = None,
) -> BaseBroker:
    """
    Create a broker instance (asynchronous convenience function).
    
    Args:
        config: Broker configuration
        session: Optional aiohttp session
        
    Returns:
        BaseBroker: Broker instance
    """
    return await BrokerFactory.create_broker_async(config, session)


async def get_broker_for_symbol(
    symbol: str,
    config: Union[BrokerConfig, BrokerConfigComplete, Dict[str, Any], str],
) -> BaseBroker:
    """
    Get a broker instance for a specific symbol.
    
    This function can be extended to support symbol-specific broker routing.
    
    Args:
        symbol: Trading symbol
        config: Broker configuration
        
    Returns:
        BaseBroker: Broker instance
    """
    return await BrokerFactory.create_broker_async(config)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Registry
    "BrokerRegistry",
    
    # Cache
    "BrokerInstanceCache",
    "CachedBroker",
    
    # Factory
    "BrokerFactory",
    
    # Convenience functions
    "create_broker",
    "create_broker_async",
    "get_broker_for_symbol",
]
