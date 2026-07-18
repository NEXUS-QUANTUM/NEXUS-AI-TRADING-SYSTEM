# trading/brokers/broker_manager.py
"""
NEXUS AI TRADING SYSTEM - Broker Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides the central broker manager that coordinates
all broker-related operations. It manages broker instances, health
monitoring, connection pooling, and provides a unified interface
for trading operations across multiple brokers.

The broker manager serves as the main entry point for all broker
interactions in the trading system.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable, Awaitable, Tuple
from enum import Enum
from contextlib import asynccontextmanager

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderStatus, OrderType
from shared.types.trading import Order, Position, AccountBalance, Trade, MarketData
from .base import (
    BaseBroker,
    BrokerConfig,
    BrokerName,
    BrokerException,
    BrokerConfigComplete,
    AccountInfo,
    OrderResponse,
    MarketDataResponse,
)
from .broker_config import BrokerConfigLoader, EnvironmentType
from .broker_factory import BrokerFactory
from .broker_connection import (
    BrokerConnectionManager,
    BrokerConnectionPool,
    ConnectionState,
    ConnectionHealth,
)
from .broker_health import (
    BrokerHealthMonitor,
    BrokerHealthChecker,
    HealthStatus,
    HealthCheckResult,
    BrokerHealthReport,
)

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class BrokerSelectionStrategy(str, Enum):
    """Strategy for selecting a broker from available instances"""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    FASTEST_LATENCY = "fastest_latency"
    HEALTHY_ONLY = "healthy_only"
    PREFERRED = "preferred"
    RANDOM = "random"


class BrokerOperationMode(str, Enum):
    """Operation mode for the broker manager"""
    SINGLE = "single"  # Single broker mode
    MULTI = "multi"    # Multiple brokers with load balancing
    FAILOVER = "failover"  # Primary/backup failover
    PARALLEL = "parallel"  # Execute on all brokers in parallel


@dataclass
class BrokerInstance:
    """Representation of a managed broker instance"""
    id: str
    config: BrokerConfigComplete
    broker: BaseBroker
    manager: BrokerConnectionManager
    health_checker: BrokerHealthChecker
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)
    usage_count: int = 0
    error_count: int = 0
    is_primary: bool = False
    priority: int = 0
    
    @property
    def is_healthy(self) -> bool:
        """Check if the broker is healthy"""
        return self.health_checker.current_status == HealthStatus.HEALTHY
    
    @property
    def is_connected(self) -> bool:
        """Check if the broker is connected"""
        return self.manager.is_connected
    
    @property
    def connection_state(self) -> ConnectionState:
        """Get the connection state"""
        return self.manager.state


# ============================================================================
# BROKER MANAGER
# ============================================================================

class BrokerManager:
    """
    Central manager for all broker operations.
    
    Features:
    - Manages multiple broker instances
    - Health monitoring and automatic failover
    - Connection pooling and management
    - Load balancing across brokers
    - Unified interface for trading operations
    - Event callbacks for broker events
    """
    
    def __init__(
        self,
        config_loader: Optional[BrokerConfigLoader] = None,
        operation_mode: BrokerOperationMode = BrokerOperationMode.SINGLE,
        selection_strategy: BrokerSelectionStrategy = BrokerSelectionStrategy.HEALTHY_ONLY,
        auto_connect: bool = True,
    ):
        """
        Initialize the broker manager.
        
        Args:
            config_loader: Configuration loader instance
            operation_mode: Operation mode
            selection_strategy: Broker selection strategy
            auto_connect: Whether to auto-connect brokers on initialization
        """
        self.config_loader = config_loader or BrokerConfigLoader()
        self.operation_mode = operation_mode
        self.selection_strategy = selection_strategy
        self.auto_connect = auto_connect
        
        self._instances: Dict[str, BrokerInstance] = {}
        self._health_monitor = BrokerHealthMonitor()
        self._pool = BrokerConnectionPool()
        self._lock = asyncio.Lock()
        self._round_robin_index = 0
        
        # Callbacks
        self._on_broker_connected: List[Callable[[str], Awaitable[None]]] = []
        self._on_broker_disconnected: List[Callable[[str], Awaitable[None]]] = []
        self._on_broker_health_change: List[Callable[[str, HealthStatus, HealthStatus], Awaitable[None]]] = []
        self._on_broker_error: List[Callable[[str, Exception], Awaitable[None]]] = []
        self._on_failover: List[Callable[[str, str], Awaitable[None]]] = []
        
        # Metrics
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "failover_events": 0,
            "start_time": datetime.utcnow(),
        }
        
        self.logger = logger
        
        # Set up alert callback
        async def on_health_change(broker_id: str, old_status: HealthStatus, new_status: HealthStatus) -> None:
            await self._handle_health_change(broker_id, old_status, new_status)
        
        self._health_monitor.set_alert_callback(on_health_change)
    
    # ========================================================================
    # CALLBACKS
    # ========================================================================
    
    def on_broker_connected(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Register callback for broker connection events"""
        self._on_broker_connected.append(callback)
    
    def on_broker_disconnected(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Register callback for broker disconnection events"""
        self._on_broker_disconnected.append(callback)
    
    def on_broker_health_change(
        self,
        callback: Callable[[str, HealthStatus, HealthStatus], Awaitable[None]],
    ) -> None:
        """Register callback for broker health change events"""
        self._on_broker_health_change.append(callback)
    
    def on_broker_error(self, callback: Callable[[str, Exception], Awaitable[None]]) -> None:
        """Register callback for broker error events"""
        self._on_broker_error.append(callback)
    
    def on_failover(self, callback: Callable[[str, str], Awaitable[None]]) -> None:
        """Register callback for failover events (old_id, new_id)"""
        self._on_failover.append(callback)
    
    async def _trigger_connected(self, broker_id: str) -> None:
        """Trigger connected callbacks"""
        for callback in self._on_broker_connected:
            try:
                await callback(broker_id)
            except Exception as e:
                self.logger.error(f"Error in connected callback: {e}")
    
    async def _trigger_disconnected(self, broker_id: str) -> None:
        """Trigger disconnected callbacks"""
        for callback in self._on_broker_disconnected:
            try:
                await callback(broker_id)
            except Exception as e:
                self.logger.error(f"Error in disconnected callback: {e}")
    
    async def _trigger_health_change(self, broker_id: str, old: HealthStatus, new: HealthStatus) -> None:
        """Trigger health change callbacks"""
        for callback in self._on_broker_health_change:
            try:
                await callback(broker_id, old, new)
            except Exception as e:
                self.logger.error(f"Error in health change callback: {e}")
    
    async def _trigger_error(self, broker_id: str, error: Exception) -> None:
        """Trigger error callbacks"""
        for callback in self._on_broker_error:
            try:
                await callback(broker_id, error)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
    
    async def _trigger_failover(self, old_id: str, new_id: str) -> None:
        """Trigger failover callbacks"""
        self._metrics["failover_events"] += 1
        for callback in self._on_failover:
            try:
                await callback(old_id, new_id)
            except Exception as e:
                self.logger.error(f"Error in failover callback: {e}")
    
    # ========================================================================
    # BROKER MANAGEMENT
    # ========================================================================
    
    async def add_broker(
        self,
        config: Union[BrokerConfigComplete, Dict[str, Any], str],
        is_primary: bool = False,
        priority: int = 0,
    ) -> str:
        """
        Add a broker to the manager.
        
        Args:
            config: Broker configuration
            is_primary: Whether this is the primary broker
            priority: Priority for selection (higher = higher priority)
            
        Returns:
            str: Broker instance ID
        """
        async with self._lock:
            # Load configuration if needed
            if isinstance(config, str):
                config = self.config_loader.get_config(config)
                if not config:
                    raise ValueError(f"Configuration not found: {config}")
            
            if isinstance(config, dict):
                config = BrokerConfigComplete(**config)
            
            if not isinstance(config, BrokerConfigComplete):
                raise ValueError(f"Invalid configuration type: {type(config)}")
            
            # Generate ID
            broker_id = f"{config.name.value}_{uuid.uuid4().hex[:8]}"
            
            # Create broker instance
            broker = await BrokerFactory.create_broker_async(config)
            
            # Create connection manager
            manager = BrokerConnectionManager(
                broker=broker,
                connection_id=broker_id,
                auto_reconnect=True,
                max_reconnect_attempts=config.retry.max_retries,
                reconnect_delay=config.retry.initial_delay,
                max_reconnect_delay=config.retry.max_delay,
            )
            
            # Create health checker
            health_checker = BrokerHealthChecker(
                broker=broker,
                broker_id=broker_id,
                check_interval=30,
            )
            
            # Set up health checker callbacks
            async def on_status_change(old: HealthStatus, new: HealthStatus) -> None:
                await self._handle_health_change(broker_id, old, new)
            
            health_checker.on_status_change(on_status_change)
            
            # Create instance record
            instance = BrokerInstance(
                id=broker_id,
                config=config,
                broker=broker,
                manager=manager,
                health_checker=health_checker,
                is_primary=is_primary,
                priority=priority,
            )
            
            self._instances[broker_id] = instance
            
            # Register with health monitor
            self._health_monitor.register_broker(
                broker=broker,
                broker_id=broker_id,
                check_interval=30,
            )
            
            # Connect if auto-connect is enabled
            if self.auto_connect:
                try:
                    await manager.connect()
                    await health_checker.start()
                    self.logger.info(f"Connected broker {broker_id}")
                except Exception as e:
                    self.logger.error(f"Failed to connect broker {broker_id}: {e}")
            
            self.logger.info(f"Added broker {broker_id} ({config.name.value})")
            return broker_id
    
    async def remove_broker(self, broker_id: str) -> bool:
        """
        Remove a broker from the manager.
        
        Args:
            broker_id: Broker instance ID
            
        Returns:
            bool: True if broker was removed
        """
        async with self._lock:
            if broker_id not in self._instances:
                return False
            
            instance = self._instances[broker_id]
            
            # Stop health monitoring
            await instance.health_checker.stop()
            
            # Disconnect
            await instance.manager.disconnect()
            
            # Unregister from health monitor
            self._health_monitor.unregister_broker(broker_id)
            
            # Remove from instances
            del self._instances[broker_id]
            
            self.logger.info(f"Removed broker {broker_id}")
            return True
    
    async def connect_all(self) -> Dict[str, bool]:
        """
        Connect all brokers.
        
        Returns:
            Dict[str, bool]: Connection results by broker ID
        """
        results = {}
        for broker_id, instance in self._instances.items():
            try:
                connected = await instance.manager.connect()
                if connected:
                    await instance.health_checker.start()
                results[broker_id] = connected
                self.logger.info(f"Broker {broker_id} connection: {connected}")
            except Exception as e:
                results[broker_id] = False
                self.logger.error(f"Failed to connect broker {broker_id}: {e}")
        return results
    
    async def disconnect_all(self) -> Dict[str, bool]:
        """
        Disconnect all brokers.
        
        Returns:
            Dict[str, bool]: Disconnection results by broker ID
        """
        results = {}
        for broker_id, instance in self._instances.items():
            try:
                await instance.health_checker.stop()
                disconnected = await instance.manager.disconnect()
                results[broker_id] = disconnected
                self.logger.info(f"Broker {broker_id} disconnection: {disconnected}")
            except Exception as e:
                results[broker_id] = False
                self.logger.error(f"Failed to disconnect broker {broker_id}: {e}")
        return results
    
    # ========================================================================
    # BROKER SELECTION
    # ========================================================================
    
    async def select_broker(
        self,
        symbol: Optional[str] = None,
        preferred_id: Optional[str] = None,
    ) -> Optional[BrokerInstance]:
        """
        Select a broker instance based on the selection strategy.
        
        Args:
            symbol: Optional symbol for symbol-specific routing
            preferred_id: Preferred broker ID
            
        Returns:
            Optional[BrokerInstance]: Selected broker instance or None
        """
        async with self._lock:
            available = []
            
            # Filter healthy instances
            for instance in self._instances.values():
                if instance.is_healthy and instance.is_connected:
                    available.append(instance)
            
            if not available:
                self.logger.warning("No healthy broker instances available")
                return None
            
            # Preferred broker
            if preferred_id:
                for instance in available:
                    if instance.id == preferred_id:
                        return instance
            
            # Symbol-specific selection (if implemented)
            if symbol:
                # This could be extended for symbol-based routing
                pass
            
            # Apply selection strategy
            if self.selection_strategy == BrokerSelectionStrategy.HEALTHY_ONLY:
                # Just return first healthy
                return available[0]
            
            elif self.selection_strategy == BrokerSelectionStrategy.ROUND_ROBIN:
                self._round_robin_index = (self._round_robin_index + 1) % len(available)
                return available[self._round_robin_index]
            
            elif self.selection_strategy == BrokerSelectionStrategy.LEAST_LOADED:
                return min(available, key=lambda x: x.usage_count)
            
            elif self.selection_strategy == BrokerSelectionStrategy.FASTEST_LATENCY:
                # Could be extended with latency tracking
                return available[0]
            
            elif self.selection_strategy == BrokerSelectionStrategy.PREFERRED:
                # Prefer primary, then higher priority
                primaries = [i for i in available if i.is_primary]
                if primaries:
                    return primaries[0]
                return max(available, key=lambda x: x.priority)
            
            elif self.selection_strategy == BrokerSelectionStrategy.RANDOM:
                import random
                return random.choice(available)
            
            # Default: first available
            return available[0]
    
    def get_instance(self, broker_id: str) -> Optional[BrokerInstance]:
        """
        Get a broker instance by ID.
        
        Args:
            broker_id: Broker instance ID
            
        Returns:
            Optional[BrokerInstance]: Broker instance or None
        """
        return self._instances.get(broker_id)
    
    def get_primary(self) -> Optional[BrokerInstance]:
        """
        Get the primary broker instance.
        
        Returns:
            Optional[BrokerInstance]: Primary broker or None
        """
        for instance in self._instances.values():
            if instance.is_primary and instance.is_healthy:
                return instance
        return None
    
    def get_all_instances(self) -> List[BrokerInstance]:
        """
        Get all broker instances.
        
        Returns:
            List[BrokerInstance]: All broker instances
        """
        return list(self._instances.values())
    
    # ========================================================================
    # HEALTH HANDLING
    # ========================================================================
    
    async def _handle_health_change(
        self,
        broker_id: str,
        old_status: HealthStatus,
        new_status: HealthStatus,
    ) -> None:
        """
        Handle health status changes.
        
        Args:
            broker_id: Broker instance ID
            old_status: Previous health status
            new_status: New health status
        """
        self.logger.info(f"Broker {broker_id} health changed: {old_status} -> {new_status}")
        
        await self._trigger_health_change(broker_id, old_status, new_status)
        
        # Handle failover for primary broker
        if old_status == HealthStatus.HEALTHY and new_status != HealthStatus.HEALTHY:
            instance = self._instances.get(broker_id)
            if instance and instance.is_primary:
                # Try to find a failover broker
                for alt_id, alt_instance in self._instances.items():
                    if alt_id != broker_id and alt_instance.is_healthy:
                        await self._trigger_failover(broker_id, alt_id)
                        break
    
    async def check_health(self, broker_id: Optional[str] = None) -> Dict[str, HealthCheckResult]:
        """
        Perform health checks.
        
        Args:
            broker_id: Optional specific broker ID
            
        Returns:
            Dict[str, HealthCheckResult]: Health check results by broker ID
        """
        results = {}
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if instance:
                result = await instance.health_checker.perform_check()
                results[broker_id] = result
        else:
            for bid, instance in self._instances.items():
                try:
                    result = await instance.health_checker.perform_check()
                    results[bid] = result
                except Exception as e:
                    self.logger.error(f"Health check failed for {bid}: {e}")
        
        return results
    
    async def get_health_report(self, broker_id: Optional[str] = None) -> Union[BrokerHealthReport, Dict[str, BrokerHealthReport]]:
        """
        Get health reports.
        
        Args:
            broker_id: Optional specific broker ID
            
        Returns:
            Union[BrokerHealthReport, Dict]: Health report(s)
        """
        if broker_id:
            instance = self._instances.get(broker_id)
            if instance:
                return await instance.health_checker.get_report()
            return None
        
        return await self._health_monitor.get_all_reports()
    
    # ========================================================================
    # TRADING OPERATIONS
    # ========================================================================
    
    async def _execute_with_broker(
        self,
        operation: Callable[[BaseBroker], Awaitable[Any]],
        symbol: Optional[str] = None,
        preferred_id: Optional[str] = None,
        retry_on_failover: bool = True,
    ) -> Any:
        """
        Execute an operation with a selected broker.
        
        Args:
            operation: Async operation to execute
            symbol: Optional symbol for routing
            preferred_id: Preferred broker ID
            retry_on_failover: Whether to retry on failover
            
        Returns:
            Any: Result of the operation
            
        Raises:
            BrokerException: If no broker is available or operation fails
        """
        self._metrics["total_requests"] += 1
        
        # Select broker
        instance = await self.select_broker(symbol, preferred_id)
        if not instance:
            self._metrics["failed_requests"] += 1
            raise BrokerException("No healthy broker available")
        
        try:
            # Update usage
            instance.last_used = datetime.utcnow()
            instance.usage_count += 1
            
            # Execute operation
            result = await operation(instance.broker)
            
            self._metrics["successful_requests"] += 1
            return result
            
        except Exception as e:
            instance.error_count += 1
            self._metrics["failed_requests"] += 1
            await self._trigger_error(instance.id, e)
            
            # Try failover if enabled
            if retry_on_failover and self.operation_mode in [
                BrokerOperationMode.FAILOVER,
                BrokerOperationMode.MULTI,
            ]:
                # Mark as unhealthy temporarily
                self.logger.warning(f"Broker {instance.id} failed, attempting failover")
                
                # Try another broker
                alt_instance = await self.select_broker(
                    symbol,
                    preferred_id=preferred_id,
                )
                if alt_instance and alt_instance.id != instance.id:
                    self.logger.info(f"Failover to broker {alt_instance.id}")
                    await self._trigger_failover(instance.id, alt_instance.id)
                    
                    # Retry with new broker
                    try:
                        alt_instance.last_used = datetime.utcnow()
                        alt_instance.usage_count += 1
                        result = await operation(alt_instance.broker)
                        self._metrics["successful_requests"] += 1
                        return result
                    except Exception as e2:
                        self.logger.error(f"Failover broker {alt_instance.id} also failed: {e2}")
            
            raise
    
    # ========================================================================
    # TRADING METHODS
    # ========================================================================
    
    async def get_account_info(
        self,
        broker_id: Optional[str] = None,
    ) -> AccountInfo:
        """
        Get account information.
        
        Args:
            broker_id: Optional specific broker ID
            
        Returns:
            AccountInfo: Account information
        """
        async def op(broker: BaseBroker) -> AccountInfo:
            return await broker.get_account_info()
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op)
    
    async def get_balances(
        self,
        broker_id: Optional[str] = None,
    ) -> List[AccountBalance]:
        """
        Get account balances.
        
        Args:
            broker_id: Optional specific broker ID
            
        Returns:
            List[AccountBalance]: Account balances
        """
        async def op(broker: BaseBroker) -> List[AccountBalance]:
            return await broker.get_balances()
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op)
    
    async def get_market_data(
        self,
        symbol: str,
        broker_id: Optional[str] = None,
    ) -> MarketDataResponse:
        """
        Get market data.
        
        Args:
            symbol: Trading symbol
            broker_id: Optional specific broker ID
            
        Returns:
            MarketDataResponse: Market data
        """
        async def op(broker: BaseBroker) -> MarketDataResponse:
            return await broker.get_market_data(symbol)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def place_order(
        self,
        order: Order,
        broker_id: Optional[str] = None,
    ) -> OrderResponse:
        """
        Place an order.
        
        Args:
            order: Order to place
            broker_id: Optional specific broker ID
            
        Returns:
            OrderResponse: Order response
        """
        async def op(broker: BaseBroker) -> OrderResponse:
            return await broker.place_order(order)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=order.symbol)
    
    async def cancel_order(
        self,
        order_id: str,
        symbol: Optional[str] = None,
        broker_id: Optional[str] = None,
    ) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            symbol: Trading symbol
            broker_id: Optional specific broker ID
            
        Returns:
            bool: True if order was cancelled
        """
        async def op(broker: BaseBroker) -> bool:
            return await broker.cancel_order(order_id, symbol)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def get_order(
        self,
        order_id: str,
        symbol: Optional[str] = None,
        broker_id: Optional[str] = None,
    ) -> OrderResponse:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            symbol: Trading symbol
            broker_id: Optional specific broker ID
            
        Returns:
            OrderResponse: Order response
        """
        async def op(broker: BaseBroker) -> OrderResponse:
            return await broker.get_order(order_id, symbol)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def get_open_orders(
        self,
        symbol: Optional[str] = None,
        broker_id: Optional[str] = None,
    ) -> List[OrderResponse]:
        """
        Get open orders.
        
        Args:
            symbol: Optional symbol filter
            broker_id: Optional specific broker ID
            
        Returns:
            List[OrderResponse]: Open orders
        """
        async def op(broker: BaseBroker) -> List[OrderResponse]:
            return await broker.get_open_orders(symbol)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def get_positions(
        self,
        symbol: Optional[str] = None,
        broker_id: Optional[str] = None,
    ) -> List[Position]:
        """
        Get open positions.
        
        Args:
            symbol: Optional symbol filter
            broker_id: Optional specific broker ID
            
        Returns:
            List[Position]: Open positions
        """
        async def op(broker: BaseBroker) -> List[Position]:
            return await broker.get_positions(symbol)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def close_position(
        self,
        symbol: str,
        broker_id: Optional[str] = None,
    ) -> bool:
        """
        Close a position.
        
        Args:
            symbol: Trading symbol
            broker_id: Optional specific broker ID
            
        Returns:
            bool: True if position was closed
        """
        async def op(broker: BaseBroker) -> bool:
            return await broker.close_position(symbol)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def get_trades(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
        broker_id: Optional[str] = None,
    ) -> List[Trade]:
        """
        Get trade history.
        
        Args:
            symbol: Optional symbol filter
            limit: Maximum number of trades
            broker_id: Optional specific broker ID
            
        Returns:
            List[Trade]: Trade history
        """
        async def op(broker: BaseBroker) -> List[Trade]:
            return await broker.get_trades(symbol, limit)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        broker_id: Optional[str] = None,
    ) -> List[MarketData]:
        """
        Get historical market data.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            limit: Maximum number of candles
            start_time: Start time
            end_time: End time
            broker_id: Optional specific broker ID
            
        Returns:
            List[MarketData]: Historical market data
        """
        async def op(broker: BaseBroker) -> List[MarketData]:
            return await broker.get_historical_data(
                symbol, timeframe, limit, start_time, end_time
            )
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    # ========================================================================
    # CONVENIENCE TRADING METHODS
    # ========================================================================
    
    async def market_buy(
        self,
        symbol: str,
        quantity: Union[float, int],
        broker_id: Optional[str] = None,
        **kwargs,
    ) -> OrderResponse:
        """
        Place a market buy order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to buy
            broker_id: Optional specific broker ID
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Order response
        """
        async def op(broker: BaseBroker) -> OrderResponse:
            return await broker.market_buy(symbol, quantity, **kwargs)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def market_sell(
        self,
        symbol: str,
        quantity: Union[float, int],
        broker_id: Optional[str] = None,
        **kwargs,
    ) -> OrderResponse:
        """
        Place a market sell order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to sell
            broker_id: Optional specific broker ID
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Order response
        """
        async def op(broker: BaseBroker) -> OrderResponse:
            return await broker.market_sell(symbol, quantity, **kwargs)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def limit_buy(
        self,
        symbol: str,
        quantity: Union[float, int],
        price: Union[float, int],
        broker_id: Optional[str] = None,
        **kwargs,
    ) -> OrderResponse:
        """
        Place a limit buy order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to buy
            price: Limit price
            broker_id: Optional specific broker ID
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Order response
        """
        async def op(broker: BaseBroker) -> OrderResponse:
            return await broker.limit_buy(symbol, quantity, price, **kwargs)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    async def limit_sell(
        self,
        symbol: str,
        quantity: Union[float, int],
        price: Union[float, int],
        broker_id: Optional[str] = None,
        **kwargs,
    ) -> OrderResponse:
        """
        Place a limit sell order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to sell
            price: Limit price
            broker_id: Optional specific broker ID
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Order response
        """
        async def op(broker: BaseBroker) -> OrderResponse:
            return await broker.limit_sell(symbol, quantity, price, **kwargs)
        
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            return await op(instance.broker)
        
        return await self._execute_with_broker(op, symbol=symbol)
    
    # ========================================================================
    # METRICS AND STATUS
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get manager metrics.
        
        Returns:
            Dict: Manager metrics
        """
        return {
            **self._metrics,
            "uptime_seconds": (datetime.utcnow() - self._metrics["start_time"]).total_seconds(),
            "active_brokers": len(self._instances),
            "healthy_brokers": sum(1 for i in self._instances.values() if i.is_healthy),
            "connected_brokers": sum(1 for i in self._instances.values() if i.is_connected),
            "operation_mode": self.operation_mode.value,
            "selection_strategy": self.selection_strategy.value,
        }
    
    def get_broker_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all brokers.
        
        Returns:
            Dict[str, Dict]: Broker status by ID
        """
        status = {}
        for broker_id, instance in self._instances.items():
            status[broker_id] = {
                "name": instance.config.name.value,
                "id": instance.id,
                "is_primary": instance.is_primary,
                "priority": instance.priority,
                "is_healthy": instance.is_healthy,
                "is_connected": instance.is_connected,
                "connection_state": instance.connection_state.value,
                "health_status": instance.health_checker.current_status.value,
                "usage_count": instance.usage_count,
                "error_count": instance.error_count,
                "created_at": instance.created_at.isoformat(),
                "last_used": instance.last_used.isoformat(),
                "account_type": instance.config.account_type.value,
                "sandbox": instance.config.sandbox_mode,
            }
        return status
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get health summary.
        
        Returns:
            Dict: Health summary
        """
        return self._health_monitor.get_summary()
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    @asynccontextmanager
    async def use_broker(self, broker_id: Optional[str] = None):
        """
        Context manager for using a broker.
        
        Args:
            broker_id: Optional specific broker ID
            
        Yields:
            BaseBroker: Broker instance
        """
        if broker_id:
            instance = self._instances.get(broker_id)
            if not instance:
                raise BrokerException(f"Broker {broker_id} not found")
            yield instance.broker
        else:
            instance = await self.select_broker()
            if not instance:
                raise BrokerException("No broker available")
            yield instance.broker
    
    async def __aenter__(self):
        """Async context manager entry"""
        if self.auto_connect:
            await self.connect_all()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect_all()
        await BrokerFactory.close_all()
    
    async def close(self) -> None:
        """Close the broker manager and clean up resources."""
        await self.disconnect_all()
        await self._health_monitor.stop_all()
        await BrokerFactory.close_all()
        self.logger.info("BrokerManager closed")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "BrokerSelectionStrategy",
    "BrokerOperationMode",
    
    # Models
    "BrokerInstance",
    
    # Manager
    "BrokerManager",
]
