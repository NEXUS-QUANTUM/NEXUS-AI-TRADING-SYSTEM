# trading/brokers/broker_connection.py
"""
NEXUS AI TRADING SYSTEM - Broker Connection Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module manages broker connections including connection pooling,
health monitoring, automatic reconnection, and connection lifecycle
management for all broker integrations.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable, Union
from contextlib import asynccontextmanager

import aiohttp
from pydantic import BaseModel, Field, validator

from shared.utilities.logger import get_logger
from shared.utilities.retry import RetryConfig, retry_async, retry_sync
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.rate_limiter import RateLimiter
from .base import BaseBroker, BrokerException, BrokerConnectionError
from .broker_config import BrokerConfigComplete, BrokerConfigLoader

logger = get_logger(__name__)


# ============================================================================
# CONNECTION STATE
# ============================================================================

class ConnectionState(str, Enum):
    """Connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    SUSPENDED = "suspended"


class ConnectionHealth(str, Enum):
    """Connection health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ConnectionInfo:
    """Information about a broker connection"""
    connection_id: str
    broker_name: str
    broker_id: str
    state: ConnectionState = ConnectionState.DISCONNECTED
    health: ConnectionHealth = ConnectionHealth.UNKNOWN
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    reconnection_attempts: int = 0
    reconnect_delay: float = 1.0
    request_count: int = 0
    error_count: int = 0
    success_count: int = 0
    latency_avg: float = 0.0
    latency_min: float = 0.0
    latency_max: float = 0.0
    latency_samples: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# CONNECTION POOL
# ============================================================================

class BrokerConnectionPool:
    """
    Manages a pool of broker connections.
    
    Features:
    - Multiple connections to the same broker
    - Round-robin load balancing
    - Health-based routing
    - Automatic connection management
    - Connection pooling with configurable limits
    """
    
    def __init__(
        self,
        max_connections_per_broker: int = 5,
        min_connections_per_broker: int = 1,
        connection_timeout: int = 30,
    ):
        """
        Initialize the connection pool.
        
        Args:
            max_connections_per_broker: Maximum connections per broker
            min_connections_per_broker: Minimum connections per broker
            connection_timeout: Connection timeout in seconds
        """
        self.max_connections_per_broker = max_connections_per_broker
        self.min_connections_per_broker = min_connections_per_broker
        self.connection_timeout = connection_timeout
        
        # Connections: broker_id -> list of connections
        self._connections: Dict[str, List[ConnectionInfo]] = {}
        self._brokers: Dict[str, BaseBroker] = {}
        self._broker_factories: Dict[str, Callable[[], Awaitable[BaseBroker]]] = {}
        self._lock = asyncio.Lock()
        
        # Health checks
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_interval: int = 30
        
        self.logger = logger
    
    async def register_broker_factory(
        self,
        broker_id: str,
        factory: Callable[[], Awaitable[BaseBroker]],
        min_connections: Optional[int] = None,
        max_connections: Optional[int] = None,
    ) -> None:
        """
        Register a broker factory for creating connections.
        
        Args:
            broker_id: Broker identifier
            factory: Async factory function that creates a broker instance
            min_connections: Minimum connections for this broker
            max_connections: Maximum connections for this broker
        """
        async with self._lock:
            self._broker_factories[broker_id] = factory
            self._connections[broker_id] = []
            
            min_conn = min_connections or self.min_connections_per_broker
            max_conn = max_connections or self.max_connections_per_broker
            
            # Initialize minimum connections
            for _ in range(min_conn):
                try:
                    conn_info = await self._create_connection(broker_id)
                    self._connections[broker_id].append(conn_info)
                except Exception as e:
                    self.logger.error(f"Failed to create initial connection for {broker_id}: {e}")
    
    async def _create_connection(self, broker_id: str) -> ConnectionInfo:
        """
        Create a new connection.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            ConnectionInfo: Connection information
            
        Raises:
            BrokerConnectionError: If connection creation fails
        """
        if broker_id not in self._broker_factories:
            raise BrokerConnectionError(f"No factory registered for broker {broker_id}")
        
        # Create connection ID
        connection_id = f"{broker_id}-{uuid.uuid4().hex[:8]}"
        
        # Create broker instance
        try:
            broker = await self._broker_factories[broker_id]()
            
            # Connect to broker
            connected = await broker.connect()
            if not connected:
                raise BrokerConnectionError(f"Failed to connect to broker {broker_id}")
            
            self._brokers[connection_id] = broker
            
            # Create connection info
            conn_info = ConnectionInfo(
                connection_id=connection_id,
                broker_name=broker.name.value if broker.name else "unknown",
                broker_id=broker_id,
                state=ConnectionState.CONNECTED,
                connected_at=datetime.utcnow(),
                health=ConnectionHealth.HEALTHY,
            )
            
            self.logger.info(f"Created connection {connection_id} for broker {broker_id}")
            return conn_info
            
        except Exception as e:
            self.logger.error(f"Failed to create connection for {broker_id}: {e}")
            raise BrokerConnectionError(f"Connection creation failed: {str(e)}")
    
    async def get_connection(
        self,
        broker_id: Optional[str] = None,
        prefer_healthy: bool = True,
    ) -> Optional[ConnectionInfo]:
        """
        Get an available connection.
        
        Args:
            broker_id: Specific broker ID (if None, returns any available)
            prefer_healthy: Whether to prefer healthy connections
            
        Returns:
            Optional[ConnectionInfo]: Connection info or None if no connection available
        """
        async with self._lock:
            # If no broker specified, get the first available
            if not broker_id:
                # Find any broker with connections
                for bid in self._connections:
                    available = self._get_available_connections(bid, prefer_healthy)
                    if available:
                        # Round-robin: return first available
                        return available[0]
                return None
            
            # Get specific broker's connections
            available = self._get_available_connections(broker_id, prefer_healthy)
            if not available:
                # Try to create a new connection if below max
                current = len(self._connections.get(broker_id, []))
                max_conn = self.max_connections_per_broker
                if current < max_conn:
                    try:
                        conn_info = await self._create_connection(broker_id)
                        self._connections[broker_id].append(conn_info)
                        return conn_info
                    except Exception:
                        pass
                return None
            
            # Return first available (round-robin)
            return available[0]
    
    def _get_available_connections(
        self,
        broker_id: str,
        prefer_healthy: bool = True,
    ) -> List[ConnectionInfo]:
        """
        Get available connections for a broker.
        
        Args:
            broker_id: Broker identifier
            prefer_healthy: Whether to prefer healthy connections
            
        Returns:
            List[ConnectionInfo]: Available connections
        """
        connections = self._connections.get(broker_id, [])
        
        # Filter by state and health
        available = []
        for conn in connections:
            if conn.state == ConnectionState.CONNECTED:
                if prefer_healthy:
                    if conn.health == ConnectionHealth.HEALTHY:
                        available.append(conn)
                else:
                    available.append(conn)
        
        return available
    
    async def release_connection(self, connection_id: str) -> None:
        """
        Release a connection back to the pool.
        
        Args:
            connection_id: Connection identifier
        """
        async with self._lock:
            # Find the connection
            for broker_id, connections in self._connections.items():
                for i, conn in enumerate(connections):
                    if conn.connection_id == connection_id:
                        # Don't remove, just mark as available
                        if conn.state == ConnectionState.DISCONNECTED:
                            # Try to reconnect if needed
                            await self._reconnect_connection(broker_id, conn)
                        return
    
    async def _reconnect_connection(self, broker_id: str, conn_info: ConnectionInfo) -> bool:
        """
        Reconnect a disconnected connection.
        
        Args:
            broker_id: Broker identifier
            conn_info: Connection information
            
        Returns:
            bool: True if reconnection was successful
        """
        if conn_info.connection_id not in self._brokers:
            return False
        
        try:
            broker = self._brokers[conn_info.connection_id]
            connected = await broker.connect()
            if connected:
                conn_info.state = ConnectionState.CONNECTED
                conn_info.connected_at = datetime.utcnow()
                conn_info.reconnection_attempts += 1
                conn_info.health = ConnectionHealth.HEALTHY
                conn_info.last_error = None
                self.logger.info(f"Reconnected {conn_info.connection_id}")
                return True
            else:
                conn_info.state = ConnectionState.ERROR
                conn_info.health = ConnectionHealth.UNHEALTHY
                return False
        except Exception as e:
            conn_info.state = ConnectionState.ERROR
            conn_info.health = ConnectionHealth.UNHEALTHY
            conn_info.last_error = str(e)
            conn_info.last_error_time = datetime.utcnow()
            self.logger.error(f"Failed to reconnect {conn_info.connection_id}: {e}")
            return False
    
    async def close_connection(self, connection_id: str) -> bool:
        """
        Close a specific connection.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            bool: True if connection was closed
        """
        async with self._lock:
            for broker_id, connections in self._connections.items():
                for i, conn in enumerate(connections):
                    if conn.connection_id == connection_id:
                        # Disconnect broker
                        if connection_id in self._brokers:
                            try:
                                await self._brokers[connection_id].disconnect()
                            except Exception as e:
                                self.logger.error(f"Error disconnecting {connection_id}: {e}")
                            finally:
                                del self._brokers[connection_id]
                        
                        # Remove from connections
                        connections.pop(i)
                        self.logger.info(f"Closed connection {connection_id}")
                        return True
            
            return False
    
    async def close_all_connections(self, broker_id: Optional[str] = None) -> int:
        """
        Close all connections for a broker or all brokers.
        
        Args:
            broker_id: Optional broker ID to close specific broker's connections
            
        Returns:
            int: Number of connections closed
        """
        async with self._lock:
            closed = 0
            
            if broker_id:
                connections = self._connections.get(broker_id, [])
                for conn in connections:
                    if await self.close_connection(conn.connection_id):
                        closed += 1
            else:
                for bid in list(self._connections.keys()):
                    connections = self._connections.get(bid, [])
                    for conn in connections:
                        if await self.close_connection(conn.connection_id):
                            closed += 1
                    # Remove empty list
                    if not self._connections.get(bid):
                        del self._connections[bid]
            
            return closed
    
    async def get_broker(self, connection_id: str) -> Optional[BaseBroker]:
        """
        Get the broker instance for a connection.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Optional[BaseBroker]: Broker instance or None
        """
        return self._brokers.get(connection_id)
    
    async def start_health_check(self, interval: int = 30) -> None:
        """
        Start periodic health checks.
        
        Args:
            interval: Health check interval in seconds
        """
        self._health_check_interval = interval
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self.logger.info(f"Started health check loop (interval={interval}s)")
    
    async def stop_health_check(self) -> None:
        """Stop the health check loop."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            self.logger.info("Stopped health check loop")
    
    async def _health_check_loop(self) -> None:
        """Health check loop."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all connections."""
        async with self._lock:
            for broker_id, connections in self._connections.items():
                for conn in connections:
                    await self._check_connection_health(broker_id, conn)
    
    async def _check_connection_health(self, broker_id: str, conn_info: ConnectionInfo) -> None:
        """
        Check the health of a specific connection.
        
        Args:
            broker_id: Broker identifier
            conn_info: Connection information
        """
        if conn_info.connection_id not in self._brokers:
            return
        
        try:
            broker = self._brokers[conn_info.connection_id]
            
            # Check health
            health = await broker.check_health()
            
            if health.get("status") == "healthy":
                conn_info.health = ConnectionHealth.HEALTHY
                if conn_info.state == ConnectionState.ERROR:
                    conn_info.state = ConnectionState.CONNECTED
            else:
                conn_info.health = ConnectionHealth.DEGRADED
                if conn_info.state == ConnectionState.CONNECTED:
                    conn_info.state = ConnectionState.ERROR
                    conn_info.last_error = "Health check failed"
                    conn_info.last_error_time = datetime.utcnow()
                
                # Try to reconnect
                if conn_info.state == ConnectionState.ERROR:
                    # Check if we should attempt reconnection
                    if conn_info.reconnection_attempts < 5:
                        await self._reconnect_connection(broker_id, conn_info)
                    else:
                        conn_info.health = ConnectionHealth.UNHEALTHY
            
            # Update metrics
            if "metrics" in health:
                metrics = health["metrics"]
                conn_info.request_count = metrics.get("requests_total", 0)
                conn_info.error_count = metrics.get("requests_failed", 0)
                conn_info.success_count = metrics.get("requests_success", 0)
                
        except Exception as e:
            conn_info.health = ConnectionHealth.UNHEALTHY
            conn_info.state = ConnectionState.ERROR
            conn_info.last_error = str(e)
            conn_info.last_error_time = datetime.utcnow()
            self.logger.error(f"Health check failed for {conn_info.connection_id}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.
        
        Returns:
            Dict: Pool statistics
        """
        stats = {
            "total_connections": 0,
            "healthy_connections": 0,
            "unhealthy_connections": 0,
            "brokers": {},
        }
        
        for broker_id, connections in self._connections.items():
            broker_stats = {
                "total": len(connections),
                "healthy": 0,
                "unhealthy": 0,
                "connections": [],
            }
            
            for conn in connections:
                broker_stats["connections"].append({
                    "id": conn.connection_id,
                    "state": conn.state.value,
                    "health": conn.health.value,
                    "connected_at": conn.connected_at.isoformat() if conn.connected_at else None,
                    "requests": conn.request_count,
                    "errors": conn.error_count,
                    "success": conn.success_count,
                })
                
                if conn.health == ConnectionHealth.HEALTHY:
                    broker_stats["healthy"] += 1
                else:
                    broker_stats["unhealthy"] += 1
            
            stats["brokers"][broker_id] = broker_stats
            stats["total_connections"] += len(connections)
            stats["healthy_connections"] += broker_stats["healthy"]
            stats["unhealthy_connections"] += broker_stats["unhealthy"]
        
        return stats
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop_health_check()
        await self.close_all_connections()


# ============================================================================
# CONNECTION MANAGER
# ============================================================================

class BrokerConnectionManager:
    """
    Single connection manager for a broker.
    
    Manages a single broker connection with automatic reconnection,
    health monitoring, and connection lifecycle management.
    """
    
    def __init__(
        self,
        broker: BaseBroker,
        connection_id: Optional[str] = None,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 30.0,
    ):
        """
        Initialize the connection manager.
        
        Args:
            broker: Broker instance
            connection_id: Optional connection ID
            auto_reconnect: Whether to automatically reconnect
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Initial reconnect delay in seconds
            max_reconnect_delay: Maximum reconnect delay in seconds
        """
        self.broker = broker
        self.connection_id = connection_id or f"conn-{uuid.uuid4().hex[:8]}"
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        
        # State
        self._state = ConnectionState.DISCONNECTED
        self._reconnect_attempts = 0
        self._reconnect_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "connect_time": 0.0,
            "disconnect_time": 0.0,
            "uptime": 0.0,
            "reconnect_attempts": 0,
            "successful_reconnects": 0,
        }
        
        # Callbacks
        self._on_connect_callbacks: List[Callable[[], Awaitable[None]]] = []
        self._on_disconnect_callbacks: List[Callable[[], Awaitable[None]]] = []
        self._on_error_callbacks: List[Callable[[Exception], Awaitable[None]]] = []
        
        self.logger = logger
    
    @property
    def state(self) -> ConnectionState:
        """Get current connection state"""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return self._state == ConnectionState.CONNECTED
    
    @property
    def is_connecting(self) -> bool:
        """Check if connecting"""
        return self._state in (ConnectionState.CONNECTING, ConnectionState.RECONNECTING)
    
    # ========================================================================
    # CALLBACK MANAGEMENT
    # ========================================================================
    
    def on_connect(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register callback for connection events"""
        self._on_connect_callbacks.append(callback)
    
    def on_disconnect(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register callback for disconnection events"""
        self._on_disconnect_callbacks.append(callback)
    
    def on_error(self, callback: Callable[[Exception], Awaitable[None]]) -> None:
        """Register callback for error events"""
        self._on_error_callbacks.append(callback)
    
    async def _trigger_on_connect(self) -> None:
        """Trigger connection callbacks"""
        for callback in self._on_connect_callbacks:
            try:
                await callback()
            except Exception as e:
                self.logger.error(f"Error in connect callback: {e}")
    
    async def _trigger_on_disconnect(self) -> None:
        """Trigger disconnection callbacks"""
        for callback in self._on_disconnect_callbacks:
            try:
                await callback()
            except Exception as e:
                self.logger.error(f"Error in disconnect callback: {e}")
    
    async def _trigger_on_error(self, error: Exception) -> None:
        """Trigger error callbacks"""
        for callback in self._on_error_callbacks:
            try:
                await callback(error)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
    
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    async def connect(self) -> bool:
        """
        Connect to the broker.
        
        Returns:
            bool: True if connection was successful
        """
        async with self._lock:
            if self._state == ConnectionState.CONNECTED:
                return True
            
            if self._state in (ConnectionState.CONNECTING, ConnectionState.RECONNECTING):
                # Wait for connection to complete
                while self.is_connecting:
                    await asyncio.sleep(0.1)
                return self._state == ConnectionState.CONNECTED
            
            self._state = ConnectionState.CONNECTING
            self.logger.info(f"Connecting to {self.broker.name}...")
            
            try:
                # Connect to broker
                connected = await self.broker.connect()
                
                if connected:
                    self._state = ConnectionState.CONNECTED
                    self._reconnect_attempts = 0
                    self._metrics["connect_time"] = time.time()
                    self.logger.info(f"Connected to {self.broker.name}")
                    
                    # Trigger callbacks
                    await self._trigger_on_connect()
                    
                    # Start health check if auto-reconnect is enabled
                    if self.auto_reconnect and not self._health_check_task:
                        self._health_check_task = asyncio.create_task(self._health_check_loop())
                    
                    return True
                else:
                    self._state = ConnectionState.ERROR
                    self.logger.error(f"Failed to connect to {self.broker.name}")
                    return False
                    
            except Exception as e:
                self._state = ConnectionState.ERROR
                self.logger.error(f"Connection error: {e}")
                await self._trigger_on_error(e)
                return False
    
    async def disconnect(self) -> bool:
        """
        Disconnect from the broker.
        
        Returns:
            bool: True if disconnection was successful
        """
        async with self._lock:
            if self._state == ConnectionState.DISCONNECTED:
                return True
            
            self._state = ConnectionState.DISCONNECTING
            self.logger.info(f"Disconnecting from {self.broker.name}...")
            
            # Cancel reconnection task
            if self._reconnect_task:
                self._reconnect_task.cancel()
                try:
                    await self._reconnect_task
                except asyncio.CancelledError:
                    pass
                self._reconnect_task = None
            
            try:
                disconnected = await self.broker.disconnect()
                
                if disconnected:
                    self._state = ConnectionState.DISCONNECTED
                    self._metrics["disconnect_time"] = time.time()
                    self._metrics["uptime"] = self._metrics["disconnect_time"] - self._metrics["connect_time"]
                    self.logger.info(f"Disconnected from {self.broker.name}")
                    
                    # Trigger callbacks
                    await self._trigger_on_disconnect()
                    
                    # Stop health check
                    if self._health_check_task:
                        self._health_check_task.cancel()
                        try:
                            await self._health_check_task
                        except asyncio.CancelledError:
                            pass
                        self._health_check_task = None
                    
                    return True
                else:
                    self.logger.error(f"Failed to disconnect from {self.broker.name}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Disconnection error: {e}")
                await self._trigger_on_error(e)
                return False
    
    async def reconnect(self) -> bool:
        """
        Reconnect to the broker.
        
        Returns:
            bool: True if reconnection was successful
        """
        async with self._lock:
            if self._state == ConnectionState.RECONNECTING:
                # Wait for reconnection to complete
                while self._state == ConnectionState.RECONNECTING:
                    await asyncio.sleep(0.1)
                return self._state == ConnectionState.CONNECTED
            
            self._state = ConnectionState.RECONNECTING
            self._reconnect_attempts += 1
            self._metrics["reconnect_attempts"] = self._reconnect_attempts
            
            self.logger.info(f"Reconnecting to {self.broker.name} (attempt {self._reconnect_attempts})...")
            
            try:
                # Disconnect first
                await self.broker.disconnect()
                
                # Reconnect
                connected = await self.broker.connect()
                
                if connected:
                    self._state = ConnectionState.CONNECTED
                    self._metrics["successful_reconnects"] += 1
                    self._reconnect_attempts = 0
                    self._metrics["connect_time"] = time.time()
                    self.logger.info(f"Reconnected to {self.broker.name}")
                    
                    # Trigger callbacks
                    await self._trigger_on_connect()
                    
                    return True
                else:
                    self._state = ConnectionState.ERROR
                    self.logger.error(f"Failed to reconnect to {self.broker.name}")
                    
                    # Schedule reconnection if auto-reconnect is enabled
                    if self.auto_reconnect and self._reconnect_attempts < self.max_reconnect_attempts:
                        self._schedule_reconnect()
                    
                    return False
                    
            except Exception as e:
                self._state = ConnectionState.ERROR
                self.logger.error(f"Reconnection error: {e}")
                await self._trigger_on_error(e)
                
                # Schedule reconnection if auto-reconnect is enabled
                if self.auto_reconnect and self._reconnect_attempts < self.max_reconnect_attempts:
                    self._schedule_reconnect()
                
                return False
    
    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt"""
        if self._reconnect_task and not self._reconnect_task.done():
            return
        
        # Calculate delay with exponential backoff
        delay = min(
            self.reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            self.max_reconnect_delay,
        )
        
        self._reconnect_task = asyncio.create_task(self._reconnect_after_delay(delay))
        self.logger.info(f"Scheduled reconnect in {delay:.1f}s (attempt {self._reconnect_attempts})")
    
    async def _reconnect_after_delay(self, delay: float) -> None:
        """Reconnect after a delay"""
        try:
            await asyncio.sleep(delay)
            await self.reconnect()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Error in scheduled reconnect: {e}")
    
    # ========================================================================
    # HEALTH CHECK
    # ========================================================================
    
    async def _health_check_loop(self) -> None:
        """Health check loop"""
        while True:
            try:
                await asyncio.sleep(30)
                
                if self._state == ConnectionState.CONNECTED:
                    health = await self.broker.check_health()
                    if health.get("status") != "healthy":
                        self.logger.warning(f"Health check failed for {self.broker.name}")
                        if self.auto_reconnect:
                            await self.reconnect()
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                if self.auto_reconnect:
                    await self.reconnect()
    
    # ========================================================================
    # OPERATIONS
    # ========================================================================
    
    async def ensure_connected(self) -> bool:
        """
        Ensure the connection is established.
        
        Returns:
            bool: True if connected
        """
        if self._state == ConnectionState.CONNECTED:
            return True
        
        if self._state in (ConnectionState.CONNECTING, ConnectionState.RECONNECTING):
            # Wait for connection
            timeout = 60
            start = time.time()
            while self.is_connecting and (time.time() - start) < timeout:
                await asyncio.sleep(0.1)
            return self._state == ConnectionState.CONNECTED
        
        return await self.connect()
    
    # ========================================================================
    # METRICS
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get connection metrics.
        
        Returns:
            Dict: Connection metrics
        """
        return {
            "connection_id": self.connection_id,
            "broker": self.broker.name.value if self.broker.name else "unknown",
            "state": self._state.value,
            "is_connected": self.is_connected,
            "reconnect_attempts": self._reconnect_attempts,
            **self._metrics,
        }
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
    
    def __repr__(self) -> str:
        return f"<BrokerConnectionManager(broker={self.broker.name}, state={self._state.value})>"


# ============================================================================
# CONNECTION FACTORY
# ============================================================================

class BrokerConnectionFactory:
    """
    Factory for creating broker connections.
    
    Creates connection managers and connection pools from configurations.
    """
    
    def __init__(self, config_loader: Optional[BrokerConfigLoader] = None):
        """
        Initialize the connection factory.
        
        Args:
            config_loader: Configuration loader instance
        """
        self.config_loader = config_loader or BrokerConfigLoader()
        self._connection_pool: Optional[BrokerConnectionPool] = None
        self._managers: Dict[str, BrokerConnectionManager] = {}
        self._lock = asyncio.Lock()
        
        self.logger = logger
    
    async def create_manager(
        self,
        config: BrokerConfigComplete,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> BrokerConnectionManager:
        """
        Create a connection manager for a broker configuration.
        
        Args:
            config: Broker configuration
            session: Optional aiohttp session
            
        Returns:
            BrokerConnectionManager: Connection manager instance
        """
        from .base import BrokerFactory
        
        # Create broker instance
        broker_config = config.to_broker_config()
        broker = BrokerFactory.get_broker(broker_config, session)
        
        # Create connection manager
        manager = BrokerConnectionManager(
            broker=broker,
            connection_id=config.id,
            auto_reconnect=True,
            max_reconnect_attempts=config.retry.max_retries,
            reconnect_delay=config.retry.initial_delay,
            max_reconnect_delay=config.retry.max_delay,
        )
        
        # Store manager
        async with self._lock:
            self._managers[config.id] = manager
        
        return manager
    
    async def create_pool(
        self,
        configs: Optional[List[BrokerConfigComplete]] = None,
    ) -> BrokerConnectionPool:
        """
        Create a connection pool from configurations.
        
        Args:
            configs: List of broker configurations
            
        Returns:
            BrokerConnectionPool: Connection pool instance
        """
        if configs is None:
            configs = self.config_loader.load_all().values()
        
        pool = BrokerConnectionPool()
        
        for config in configs:
            if not config.enabled:
                continue
            
            # Create factory for this broker
            async def create_broker(cfg=config) -> BaseBroker:
                from .base import BrokerFactory
                return BrokerFactory.get_broker(cfg.to_broker_config())
            
            # Register factory
            await pool.register_broker_factory(
                broker_id=config.id,
                factory=create_broker,
                min_connections=1,
                max_connections=self.config_loader.max_connections_per_broker,
            )
        
        self._connection_pool = pool
        return pool
    
    def get_manager(self, connection_id: str) -> Optional[BrokerConnectionManager]:
        """
        Get a connection manager by ID.
        
        Args:
            connection_id: Connection manager ID
            
        Returns:
            Optional[BrokerConnectionManager]: Connection manager or None
        """
        return self._managers.get(connection_id)
    
    async def close_all_managers(self) -> int:
        """
        Close all connection managers.
        
        Returns:
            int: Number of managers closed
        """
        closed = 0
        for manager in list(self._managers.values()):
            try:
                await manager.disconnect()
                closed += 1
            except Exception as e:
                self.logger.error(f"Error closing manager: {e}")
        return closed
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_all_managers()
        if self._connection_pool:
            await self._connection_pool.__aexit__(exc_type, exc_val, exc_tb)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "ConnectionState",
    "ConnectionHealth",
    
    # Models
    "ConnectionInfo",
    
    # Connection Pool
    "BrokerConnectionPool",
    
    # Connection Manager
    "BrokerConnectionManager",
    
    # Factory
    "BrokerConnectionFactory",
]
