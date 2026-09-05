"""
Web3 Provider Module
======================

This module provides Web3 provider management for connecting to Ethereum and
EVM-compatible blockchain nodes. It supports multiple provider types including
HTTP, WebSocket, and IPC, with automatic failover, load balancing, and
connection pooling.
"""

import asyncio
import json
import logging
import random
import threading
import time
from typing import Dict, List, Optional, Union, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from web3 import Web3
from web3.middleware import geth_poa_middleware, http_retry_request_middleware
from web3.providers import HTTPProvider, WebsocketProvider, IPCProvider
from web3.types import BlockIdentifier, TxParams
from eth_utils import to_checksum_address

from trading.bots.swing_bot.utils.cache import MemoryCache
from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.converters import to_int, to_float, to_str
from trading.bots.swing_bot.utils.helpers import load_json, save_json

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Provider connection types."""
    HTTP = "http"
    WEBSOCKET = "websocket"
    IPC = "ipc"
    AUTO = "auto"


class ProviderStatus(Enum):
    """Provider status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    DEGRADED = "degraded"


@dataclass
class ProviderConfig:
    """Configuration for a blockchain provider."""
    name: str
    url: str
    provider_type: ProviderType = ProviderType.HTTP
    weight: int = 1
    timeout: int = 30
    max_retries: int = 3
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    is_websocket: bool = False
    headers: Dict[str, str] = field(default_factory=dict)
    request_kwargs: Dict[str, Any] = field(default_factory=dict)
    websocket_kwargs: Dict[str, Any] = field(default_factory=dict)
    rate_limit: int = 0  # Requests per second, 0 for unlimited
    max_connections: int = 10
    connection_timeout: int = 10
    health_check_interval: int = 30
    retry_on_failure: bool = True
    failover_priority: int = 10


@dataclass
class ProviderStats:
    """Statistics for a provider."""
    name: str
    status: ProviderStatus
    connected_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    last_response_time: float = 0.0
    error_rate: float = 0.0
    last_error: Optional[str] = None
    uptime: float = 0.0
    block_number: int = 0
    is_healthy: bool = True


class Web3Provider:
    """
    Web3 provider wrapper with connection management and health monitoring.
    
    Supports HTTP, WebSocket, and IPC providers with automatic reconnection,
    health checks, and performance tracking.
    """
    
    def __init__(self, config: ProviderConfig):
        """
        Initialize the Web3 provider.
        
        Args:
            config: Provider configuration.
        """
        self.config = config
        self._w3: Optional[Web3] = None
        self._status = ProviderStatus.DISCONNECTED
        self._stats = ProviderStats(name=config.name, status=ProviderStatus.DISCONNECTED)
        self._lock = threading.RLock()
        self._connected_at: Optional[datetime] = None
        self._last_health_check: Optional[datetime] = None
        self._request_times: deque = deque(maxlen=100)
        self._error_count = 0
        self._total_requests = 0
        
        # Connection parameters
        self._is_websocket = config.is_websocket or config.provider_type == ProviderType.WEBSOCKET
        
        logger.info(f"Initialized provider: {config.name} ({config.url})")
    
    @property
    def w3(self) -> Optional[Web3]:
        """Get the Web3 instance."""
        with self._lock:
            return self._w3
    
    @property
    def status(self) -> ProviderStatus:
        """Get the current status."""
        return self._status
    
    @property
    def is_connected(self) -> bool:
        """Check if the provider is connected."""
        return self._status == ProviderStatus.CONNECTED
    
    @property
    def stats(self) -> ProviderStats:
        """Get provider statistics."""
        with self._lock:
            return self._stats
    
    def connect(self) -> bool:
        """
        Connect to the provider.
        
        Returns:
            True if connected, False otherwise.
        """
        with self._lock:
            if self._status == ProviderStatus.CONNECTED:
                return True
            
            self._status = ProviderStatus.CONNECTING
            logger.info(f"Connecting to provider: {self.config.name}")
            
            try:
                # Build provider
                provider = self._build_provider()
                
                # Create Web3 instance
                self._w3 = Web3(provider)
                
                # Inject middleware
                self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                if self.config.max_retries > 1:
                    self._w3.middleware_onion.add(http_retry_request_middleware)
                
                # Test connection
                if self._w3.is_connected():
                    self._status = ProviderStatus.CONNECTED
                    self._connected_at = datetime.now()
                    self._stats.status = ProviderStatus.CONNECTED
                    self._stats.connected_at = self._connected_at
                    self._stats.is_healthy = True
                    
                    # Get initial block number
                    try:
                        self._stats.block_number = self._w3.eth.block_number
                    except:
                        pass
                    
                    logger.info(f"Connected to provider: {self.config.name}")
                    return True
                else:
                    self._status = ProviderStatus.ERROR
                    self._stats.status = ProviderStatus.ERROR
                    logger.error(f"Failed to connect to provider: {self.config.name}")
                    return False
                    
            except Exception as e:
                self._status = ProviderStatus.ERROR
                self._stats.status = ProviderStatus.ERROR
                self._stats.last_error = str(e)
                self._stats.is_healthy = False
                logger.error(f"Connection error for {self.config.name}: {e}")
                return False
    
    def _build_provider(self) -> Union[HTTPProvider, WebsocketProvider, IPCProvider]:
        """
        Build the appropriate provider.
        
        Returns:
            Web3 provider instance.
        """
        if self.config.provider_type == ProviderType.WEBSOCKET:
            return self._build_websocket_provider()
        elif self.config.provider_type == ProviderType.IPC:
            return self._build_ipc_provider()
        else:
            return self._build_http_provider()
    
    def _build_http_provider(self) -> HTTPProvider:
        """Build an HTTP provider."""
        request_kwargs = {
            'timeout': self.config.timeout,
            **(self.config.request_kwargs or {})
        }
        
        headers = {
            'Content-Type': 'application/json',
            **(self.config.headers or {})
        }
        
        if self.config.api_key:
            headers['Authorization'] = f'Bearer {self.config.api_key}'
        
        if headers:
            request_kwargs['headers'] = headers
        
        return HTTPProvider(
            self.config.url,
            request_kwargs=request_kwargs
        )
    
    def _build_websocket_provider(self) -> WebsocketProvider:
        """Build a WebSocket provider."""
        websocket_kwargs = {
            'timeout': self.config.timeout,
            'max_size': 2**26,
            **(self.config.websocket_kwargs or {})
        }
        
        if self.config.api_key:
            # Add API key to URL if needed
            url = self.config.url
            if '?' in url:
                url += f'&api_key={self.config.api_key}'
            else:
                url += f'?api_key={self.config.api_key}'
            websocket_url = url
        else:
            websocket_url = self.config.url
        
        return WebsocketProvider(
            websocket_url,
            websocket_kwargs=websocket_kwargs
        )
    
    def _build_ipc_provider(self) -> IPCProvider:
        """Build an IPC provider."""
        return IPCProvider(
            self.config.url,
            timeout=self.config.timeout
        )
    
    def disconnect(self) -> None:
        """Disconnect the provider."""
        with self._lock:
            if self._status != ProviderStatus.CONNECTED:
                return
            
            self._status = ProviderStatus.DISCONNECTED
            self._stats.status = ProviderStatus.DISCONNECTED
            self._stats.is_healthy = False
            
            # Close WebSocket if needed
            if self._w3 and self._is_websocket:
                try:
                    if hasattr(self._w3.provider, 'close'):
                        self._w3.provider.close()
                except:
                    pass
            
            self._w3 = None
            logger.info(f"Disconnected from provider: {self.config.name}")
    
    def health_check(self) -> bool:
        """
        Perform a health check on the provider.
        
        Returns:
            True if healthy, False otherwise.
        """
        with self._lock:
            self._last_health_check = datetime.now()
            
            if self._w3 is None:
                self._stats.is_healthy = False
                return self.connect()
            
            try:
                # Test connection with a simple call
                if self._w3.is_connected():
                    # Get block number to verify responsiveness
                    block = self._w3.eth.block_number
                    self._stats.block_number = block
                    self._stats.is_healthy = True
                    
                    if self._status != ProviderStatus.CONNECTED:
                        self._status = ProviderStatus.CONNECTED
                        self._stats.status = ProviderStatus.CONNECTED
                    
                    return True
                else:
                    self._status = ProviderStatus.DISCONNECTED
                    self._stats.status = ProviderStatus.DISCONNECTED
                    self._stats.is_healthy = False
                    # Try reconnect
                    if self.config.retry_on_failure:
                        return self.connect()
                    return False
                    
            except Exception as e:
                self._stats.last_error = str(e)
                self._stats.is_healthy = False
                self._status = ProviderStatus.ERROR
                self._stats.status = ProviderStatus.ERROR
                logger.warning(f"Health check failed for {self.config.name}: {e}")
                
                if self.config.retry_on_failure:
                    return self.connect()
                return False
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with the Web3 instance.
        
        Args:
            func: Function to execute (takes Web3 as first argument).
            *args, **kwargs: Arguments for the function.
            
        Returns:
            Result of the function.
            
        Raises:
            ConnectionError: If provider is not connected.
        """
        start_time = time.time()
        
        with self._lock:
            if self._w3 is None or not self.is_connected:
                # Try to reconnect
                if self.config.retry_on_failure:
                    if not self.connect():
                        raise ConnectionError(f"Provider {self.config.name} is not connected")
                else:
                    raise ConnectionError(f"Provider {self.config.name} is not connected")
            
            try:
                result = func(self._w3, *args, **kwargs)
                
                # Update stats
                self._update_stats(start_time, True)
                return result
                
            except Exception as e:
                self._update_stats(start_time, False, str(e))
                raise
    
    def _update_stats(self, start_time: float, success: bool, error: Optional[str] = None) -> None:
        """
        Update provider statistics.
        
        Args:
            start_time: Request start time.
            success: Whether the request succeeded.
            error: Error message if failed.
        """
        response_time = time.time() - start_time
        
        with self._lock:
            self._stats.last_used = datetime.now()
            self._stats.request_count += 1
            
            if success:
                self._stats.success_count += 1
                self._stats.last_response_time = response_time
                self._stats.avg_response_time = (
                    (self._stats.avg_response_time * (self._stats.success_count - 1) + response_time)
                    / self._stats.success_count
                )
            else:
                self._stats.error_count += 1
                self._stats.last_error = error
            
            self._stats.error_rate = self._stats.error_count / self._stats.request_count if self._stats.request_count > 0 else 0
    
    def __repr__(self) -> str:
        return f"Web3Provider(name={self.config.name}, status={self._status.value})"


class Web3ProviderPool:
    """
    Pool of Web3 providers with load balancing and failover.
    
    Supports:
    - Multiple providers with weight-based load balancing
    - Automatic failover on connection errors
    - Health checking and recovery
    - Connection pooling
    - Rate limiting
    """
    
    def __init__(
        self,
        providers: List[ProviderConfig],
        load_balancing: str = "weighted_round_robin",
        failover_enabled: bool = True,
        health_check_interval: int = 30,
        retry_attempts: int = 3
    ):
        """
        Initialize the provider pool.
        
        Args:
            providers: List of provider configurations.
            load_balancing: Load balancing strategy.
            failover_enabled: Enable automatic failover.
            health_check_interval: Health check interval in seconds.
            retry_attempts: Number of retry attempts on failure.
        """
        self._providers: Dict[str, Web3Provider] = {}
        self._provider_list: List[Web3Provider] = []
        self._load_balancing = load_balancing
        self._failover_enabled = failover_enabled
        self._health_check_interval = health_check_interval
        self._retry_attempts = retry_attempts
        
        self._lock = threading.RLock()
        self._current_index = 0
        self._running = False
        self._health_thread: Optional[threading.Thread] = None
        
        # Add providers
        for config in providers:
            self.add_provider(config)
        
        # Start health check thread
        self._start_health_checks()
        
        logger.info(f"Web3ProviderPool initialized with {len(self._providers)} providers")
    
    def add_provider(self, config: ProviderConfig) -> Web3Provider:
        """
        Add a provider to the pool.
        
        Args:
            config: Provider configuration.
            
        Returns:
            Web3Provider instance.
        """
        with self._lock:
            provider = Web3Provider(config)
            self._providers[config.name] = provider
            self._provider_list.append(provider)
            
            # Connect if not connected
            if not provider.is_connected:
                provider.connect()
            
            # Sort by failover priority
            self._provider_list.sort(key=lambda p: p.config.failover_priority, reverse=True)
            
            logger.info(f"Added provider to pool: {config.name}")
            return provider
    
    def remove_provider(self, name: str) -> bool:
        """
        Remove a provider from the pool.
        
        Args:
            name: Provider name.
            
        Returns:
            True if removed, False otherwise.
        """
        with self._lock:
            if name not in self._providers:
                return False
            
            provider = self._providers.pop(name)
            self._provider_list.remove(provider)
            provider.disconnect()
            
            logger.info(f"Removed provider from pool: {name}")
            return True
    
    def _start_health_checks(self) -> None:
        """Start the health check thread."""
        if self._running:
            return
        
        self._running = True
        self._health_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="web3_health_check"
        )
        self._health_thread.start()
    
    def _health_check_loop(self) -> None:
        """Health check loop."""
        while self._running:
            try:
                with self._lock:
                    for provider in self._provider_list:
                        provider.health_check()
                
                time.sleep(self._health_check_interval)
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                time.sleep(5)
    
    def _get_provider(self) -> Optional[Web3Provider]:
        """
        Get a provider based on load balancing strategy.
        
        Returns:
            Web3Provider or None.
        """
        with self._lock:
            if not self._provider_list:
                return None
            
            # Filter healthy providers
            healthy = [p for p in self._provider_list if p.is_connected]
            
            if not healthy:
                # Try to reconnect all providers
                for provider in self._provider_list:
                    provider.connect()
                healthy = [p for p in self._provider_list if p.is_connected]
                
                if not healthy:
                    return None
            
            if self._load_balancing == "round_robin":
                # Round-robin selection
                provider = healthy[self._current_index % len(healthy)]
                self._current_index += 1
                return provider
                
            elif self._load_balancing == "weighted_round_robin":
                # Weighted round-robin
                total_weight = sum(p.config.weight for p in healthy)
                if total_weight == 0:
                    return healthy[0]
                
                # Simple weighted selection
                random_weight = random.random() * total_weight
                cumulative = 0
                for provider in healthy:
                    cumulative += provider.config.weight
                    if cumulative >= random_weight:
                        return provider
                return healthy[0]
                
            elif self._load_balancing == "least_used":
                # Least used provider
                return min(healthy, key=lambda p: p.stats.request_count)
                
            elif self._load_balancing == "fastest":
                # Fastest provider
                return min(healthy, key=lambda p: p.stats.avg_response_time or float('inf'))
                
            else:
                # Default: round-robin
                provider = healthy[self._current_index % len(healthy)]
                self._current_index += 1
                return provider
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with a provider from the pool.
        
        Args:
            func: Function to execute.
            *args, **kwargs: Arguments for the function.
            
        Returns:
            Result of the function.
            
        Raises:
            ConnectionError: If no provider is available.
        """
        attempts = 0
        last_error = None
        
        while attempts < self._retry_attempts:
            provider = self._get_provider()
            
            if provider is None:
                raise ConnectionError("No providers available")
            
            try:
                return provider.execute(func, *args, **kwargs)
            except Exception as e:
                last_error = e
                attempts += 1
                
                if not self._failover_enabled:
                    raise
                
                logger.warning(f"Provider {provider.config.name} failed (attempt {attempts}): {e}")
                provider.health_check()
        
        raise ConnectionError(f"All providers failed: {last_error}") from last_error
    
    def get_web3(self) -> Web3:
        """
        Get a Web3 instance from the pool.
        
        Returns:
            Web3 instance.
        """
        provider = self._get_provider()
        if provider is None:
            raise ConnectionError("No providers available")
        
        if provider.w3 is None:
            raise ConnectionError(f"Provider {provider.config.name} has no Web3 instance")
        
        return provider.w3
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get pool statistics.
        
        Returns:
            Statistics dictionary.
        """
        with self._lock:
            return {
                'provider_count': len(self._provider_list),
                'connected_count': sum(1 for p in self._provider_list if p.is_connected),
                'healthy_count': sum(1 for p in self._provider_list if p.stats.is_healthy),
                'load_balancing': self._load_balancing,
                'failover_enabled': self._failover_enabled,
                'providers': {
                    p.config.name: {
                        'status': p.status.value,
                        'is_healthy': p.stats.is_healthy,
                        'request_count': p.stats.request_count,
                        'error_rate': p.stats.error_rate,
                        'avg_response_time': p.stats.avg_response_time,
                        'block_number': p.stats.block_number,
                        'weight': p.config.weight,
                        'failover_priority': p.config.failover_priority
                    }
                    for p in self._provider_list
                }
            }
    
    def shutdown(self) -> None:
        """Shutdown the provider pool."""
        self._running = False
        
        if self._health_thread:
            self._health_thread.join(timeout=5)
        
        with self._lock:
            for provider in self._provider_list:
                provider.disconnect()
        
        logger.info("Web3ProviderPool shutdown complete")


class Web3ProviderManager:
    """
    Singleton manager for Web3 providers.
    
    Manages provider configurations, connections, and provides access
    to Web3 instances across the application.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._pools: Dict[str, Web3ProviderPool] = {}
        self._active_pool: Optional[str] = None
        self._config: Optional[Dict[str, Any]] = None
        self._lock = threading.RLock()
        
        logger.info("Web3ProviderManager initialized")
    
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the manager with configuration.
        
        Args:
            config: Configuration dictionary.
        """
        with self._lock:
            self._config = config
            
            # Create pools from config
            pools_config = config.get('pools', {})
            
            for pool_name, pool_config in pools_config.items():
                providers = []
                for provider_config in pool_config.get('providers', []):
                    providers.append(ProviderConfig(
                        name=provider_config.get('name', 'unknown'),
                        url=provider_config.get('url', ''),
                        provider_type=ProviderType(provider_config.get('type', 'http')),
                        weight=provider_config.get('weight', 1),
                        timeout=provider_config.get('timeout', 30),
                        max_retries=provider_config.get('max_retries', 3),
                        api_key=provider_config.get('api_key'),
                        api_secret=provider_config.get('api_secret'),
                        headers=provider_config.get('headers', {}),
                        failover_priority=provider_config.get('failover_priority', 10),
                        rate_limit=provider_config.get('rate_limit', 0),
                        max_connections=provider_config.get('max_connections', 10)
                    ))
                
                if providers:
                    pool = Web3ProviderPool(
                        providers=providers,
                        load_balancing=pool_config.get('load_balancing', 'weighted_round_robin'),
                        failover_enabled=pool_config.get('failover_enabled', True),
                        health_check_interval=pool_config.get('health_check_interval', 30),
                        retry_attempts=pool_config.get('retry_attempts', 3)
                    )
                    self._pools[pool_name] = pool
            
            # Set active pool
            if pool_config:
                self._active_pool = config.get('default_pool', list(self._pools.keys())[0])
    
    def get_pool(self, name: Optional[str] = None) -> Optional[Web3ProviderPool]:
        """
        Get a provider pool.
        
        Args:
            name: Pool name (uses active pool if None).
            
        Returns:
            Web3ProviderPool or None.
        """
        with self._lock:
            if name is None:
                name = self._active_pool
            
            return self._pools.get(name)
    
    def get_web3(self, pool_name: Optional[str] = None) -> Web3:
        """
        Get a Web3 instance from the active pool.
        
        Args:
            pool_name: Pool name.
            
        Returns:
            Web3 instance.
        """
        pool = self.get_pool(pool_name)
        if pool is None:
            raise ConnectionError("No provider pool available")
        
        return pool.get_web3()
    
    def execute(self, func: Callable, pool_name: Optional[str] = None, *args, **kwargs) -> Any:
        """
        Execute a function with the Web3 instance.
        
        Args:
            func: Function to execute.
            pool_name: Pool name.
            *args, **kwargs: Arguments for the function.
            
        Returns:
            Result of the function.
        """
        pool = self.get_pool(pool_name)
        if pool is None:
            raise ConnectionError("No provider pool available")
        
        return pool.execute(func, *args, **kwargs)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get manager statistics.
        
        Returns:
            Statistics dictionary.
        """
        with self._lock:
            stats = {
                'pools': {},
                'active_pool': self._active_pool
            }
            
            for name, pool in self._pools.items():
                stats['pools'][name] = pool.get_stats()
            
            return stats
    
    def shutdown(self) -> None:
        """Shutdown all provider pools."""
        with self._lock:
            for pool in self._pools.values():
                pool.shutdown()
            self._pools.clear()
        
        logger.info("Web3ProviderManager shutdown complete")


# Global provider manager instance
_provider_manager: Optional[Web3ProviderManager] = None


def get_provider_manager() -> Web3ProviderManager:
    """Get the global provider manager instance."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = Web3ProviderManager()
    return _provider_manager


def create_web3_provider(config: Dict[str, Any]) -> Web3Provider:
    """
    Create a Web3 provider from configuration.
    
    Args:
        config: Provider configuration dictionary.
        
    Returns:
        Web3Provider instance.
    """
    provider_config = ProviderConfig(
        name=config.get('name', 'unknown'),
        url=config.get('url', ''),
        provider_type=ProviderType(config.get('type', 'http')),
        weight=config.get('weight', 1),
        timeout=config.get('timeout', 30),
        max_retries=config.get('max_retries', 3),
        api_key=config.get('api_key'),
        api_secret=config.get('api_secret'),
        headers=config.get('headers', {}),
        failover_priority=config.get('failover_priority', 10),
        rate_limit=config.get('rate_limit', 0),
        max_connections=config.get('max_connections', 10)
    )
    
    return Web3Provider(provider_config)


def create_provider_pool(providers: List[Dict[str, Any]], **kwargs) -> Web3ProviderPool:
    """
    Create a provider pool from configuration.
    
    Args:
        providers: List of provider configurations.
        **kwargs: Additional pool parameters.
        
    Returns:
        Web3ProviderPool instance.
    """
    provider_configs = []
    for config in providers:
        provider_configs.append(ProviderConfig(
            name=config.get('name', 'unknown'),
            url=config.get('url', ''),
            provider_type=ProviderType(config.get('type', 'http')),
            weight=config.get('weight', 1),
            timeout=config.get('timeout', 30),
            max_retries=config.get('max_retries', 3),
            api_key=config.get('api_key'),
            api_secret=config.get('api_secret'),
            headers=config.get('headers', {}),
            failover_priority=config.get('failover_priority', 10)
        ))
    
    return Web3ProviderPool(
        providers=provider_configs,
        load_balancing=kwargs.get('load_balancing', 'weighted_round_robin'),
        failover_enabled=kwargs.get('failover_enabled', True),
        health_check_interval=kwargs.get('health_check_interval', 30),
        retry_attempts=kwargs.get('retry_attempts', 3)
    )


__all__ = [
    'ProviderType',
    'ProviderStatus',
    'ProviderConfig',
    'ProviderStats',
    'Web3Provider',
    'Web3ProviderPool',
    'Web3ProviderManager',
    'get_provider_manager',
    'create_web3_provider',
    'create_provider_pool'
]
