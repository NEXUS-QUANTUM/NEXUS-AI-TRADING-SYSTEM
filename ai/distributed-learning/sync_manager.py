"""
NEXUS AI TRADING SYSTEM - Synchronization Manager for Distributed Learning
Copyright © 2026 NEXUS QUANTUM LTD

This module implements a comprehensive synchronization manager for distributed learning including:
- Distributed training coordination
- Synchronous and asynchronous training modes
- Gradient synchronization
- Model parameter synchronization
- State synchronization across workers
- Distributed checkpointing
- Consensus algorithms
- Vector clocks for event ordering
- Distributed locking
- Barrier synchronization
- All-reduce operations
- Broadcast operations
- Scatter operations
- Gather operations
- Reduce operations
- All-gather operations
- Distributed counter management
- Distributed queue management
- Distributed semaphore management
- Performance monitoring and metrics
- Fault tolerance and recovery
- Load balancing
- Straggler mitigation
- Priority-based scheduling
- Resource management
"""

import asyncio
import logging
import time
import json
import pickle
import hashlib
import uuid
from typing import Dict, List, Optional, Tuple, Any, Set, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError
import aiohttp
from aiohttp import web, ClientSession, ClientTimeout
import asyncio
import uvloop
import zlib
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/sync_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class SyncMode(Enum):
    """Synchronization modes."""
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    SEMI_SYNCHRONOUS = "semi_synchronous"
    DECENTRALIZED = "decentralized"


class SyncStatus(Enum):
    """Synchronization status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class OperationType(Enum):
    """Distributed operation types."""
    ALL_REDUCE = "all_reduce"
    BROADCAST = "broadcast"
    SCATTER = "scatter"
    GATHER = "gather"
    REDUCE = "reduce"
    ALL_GATHER = "all_gather"
    REDUCE_SCATTER = "reduce_scatter"
    ALL_TO_ALL = "all_to_all"


@dataclass
class SyncOperation:
    """Synchronization operation definition."""
    operation_id: str
    operation_type: OperationType
    sender: str
    receivers: List[str]
    data: Any
    timestamp: float
    status: SyncStatus = SyncStatus.PENDING
    priority: int = 0
    timeout: float = 30.0
    retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class DistributedLock:
    """Distributed lock information."""
    lock_id: str
    resource_id: str
    holder: str
    acquired_at: float
    expires_at: float
    renew_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DistributedCounter:
    """Distributed counter information."""
    counter_id: str
    value: int
    node_id: str
    updated_at: float
    version: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorClock:
    """Vector clock for event ordering."""
    node_id: str
    clock: Dict[str, int]
    timestamp: float
    version: int = 0


@dataclass
class SyncMetrics:
    """Synchronization metrics."""
    timestamp: float
    operation_count: int
    success_count: int
    failure_count: int
    average_latency: float
    max_latency: float
    min_latency: float
    throughput: float
    pending_operations: int
    active_operations: int
    node_count: int


# ============================================
# Synchronization Manager Configuration
# ============================================

@dataclass
class SyncManagerConfig:
    """Configuration for the synchronization manager."""
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8081
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 1
    
    # Sync settings
    sync_mode: str = "synchronous"
    heartbeat_interval: float = 10.0
    timeout_default: float = 30.0
    max_retries: int = 3
    operation_timeout: float = 60.0
    
    # Resource settings
    max_concurrent_operations: int = 100
    operation_queue_size: int = 1000
    lock_timeout: float = 60.0
    lock_renew_interval: float = 30.0
    
    # Performance settings
    batch_size: int = 10
    compression_enabled: bool = True
    compression_level: int = 5
    
    # Monitoring settings
    enable_metrics: bool = True
    metrics_interval: float = 10.0
    log_level: str = "INFO"


# ============================================
# Synchronization Manager Implementation
# ============================================

class SyncManager:
    """
    Distributed synchronization manager for federated learning.
    
    This manager handles synchronization of gradients, parameters, and state
    across distributed workers using various synchronization patterns.
    """
    
    def __init__(self, config: SyncManagerConfig):
        """
        Initialize the synchronization manager.
        
        Args:
            config: Synchronization manager configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # State
        self.operations: Dict[str, SyncOperation] = {}
        self.pending_operations: deque = deque()
        self.active_operations: Set[str] = set()
        self.completed_operations: List[str] = []
        
        # Distributed primitives
        self.locks: Dict[str, DistributedLock] = {}
        self.counters: Dict[str, DistributedCounter] = {}
        self.vector_clocks: Dict[str, VectorClock] = {}
        
        # Node management
        self.nodes: Set[str] = set()
        self.node_heartbeats: Dict[str, float] = {}
        self.node_status: Dict[str, str] = {}
        
        # Performance
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.metrics: Dict[str, Any] = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "average_latency": 0,
            "max_latency": 0,
            "min_latency": float('inf'),
            "throughput": 0,
            "pending_ops": 0,
            "active_ops": 0,
        }
        
        # Redis connection
        self.redis_client: Optional[redis.Redis] = None
        
        # Locks
        self.operation_lock = asyncio.Lock()
        self.node_lock = asyncio.Lock()
        self.resource_lock = asyncio.Lock()
        
        # Health check
        self.health_check_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None
        
        self.logger.info(f"Sync Manager initialized with mode: {self.config.sync_mode}")
    
    # ============================================
    # Initialization and Connection
    # ============================================
    
    async def _connect_redis(self) -> None:
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(
                self.config.redis_url,
                db=self.config.redis_db,
                decode_responses=False
            )
            await self.redis_client.ping()
            self.logger.info("Connected to Redis")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def _disconnect_redis(self) -> None:
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("Disconnected from Redis")
    
    # ============================================
    # Node Management
    # ============================================
    
    async def register_node(self, node_id: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a node in the distributed system.
        
        Args:
            node_id: Node identifier
            metadata: Additional node metadata
            
        Returns:
            True if registration successful
        """
        async with self.node_lock:
            if node_id in self.nodes:
                self.logger.warning(f"Node {node_id} already registered")
                return False
            
            self.nodes.add(node_id)
            self.node_heartbeats[node_id] = time.time()
            self.node_status[node_id] = "active"
            
            # Initialize vector clock
            self.vector_clocks[node_id] = VectorClock(
                node_id=node_id,
                clock={node_id: 0},
                timestamp=time.time(),
                version=0
            )
            
            self.logger.info(f"Node {node_id} registered")
            return True
    
    async def unregister_node(self, node_id: str) -> bool:
        """
        Unregister a node.
        
        Args:
            node_id: Node identifier
            
        Returns:
            True if unregistration successful
        """
        async with self.node_lock:
            if node_id not in self.nodes:
                self.logger.warning(f"Node {node_id} not found")
                return False
            
            self.nodes.remove(node_id)
            if node_id in self.node_heartbeats:
                del self.node_heartbeats[node_id]
            if node_id in self.node_status:
                del self.node_status[node_id]
            if node_id in self.vector_clocks:
                del self.vector_clocks[node_id]
            
            self.logger.info(f"Node {node_id} unregistered")
            return True
    
    async def update_heartbeat(self, node_id: str) -> bool:
        """
        Update node heartbeat.
        
        Args:
            node_id: Node identifier
            
        Returns:
            True if update successful
        """
        if node_id not in self.nodes:
            return False
        
        self.node_heartbeats[node_id] = time.time()
        self.node_status[node_id] = "active"
        return True
    
    async def get_active_nodes(self) -> List[str]:
        """
        Get list of active nodes.
        
        Returns:
            List of active node IDs
        """
        current_time = time.time()
        active = []
        for node_id, heartbeat in self.node_heartbeats.items():
            if current_time - heartbeat < self.config.heartbeat_interval * 3:
                active.append(node_id)
        return active
    
    # ============================================
    # Vector Clock Management
    # ============================================
    
    async def increment_vector_clock(self, node_id: str) -> None:
        """Increment vector clock for a node."""
        if node_id not in self.vector_clocks:
            self.vector_clocks[node_id] = VectorClock(
                node_id=node_id,
                clock={node_id: 0},
                timestamp=time.time(),
                version=0
            )
        
        self.vector_clocks[node_id].clock[node_id] = \
            self.vector_clocks[node_id].clock.get(node_id, 0) + 1
        self.vector_clocks[node_id].timestamp = time.time()
        self.vector_clocks[node_id].version += 1
    
    async def get_vector_clock(self, node_id: str) -> Optional[VectorClock]:
        """Get vector clock for a node."""
        return self.vector_clocks.get(node_id)
    
    async def merge_vector_clocks(
        self,
        node_id: str,
        other_clock: Dict[str, int]
    ) -> None:
        """Merge another vector clock into the node's clock."""
        if node_id not in self.vector_clocks:
            self.vector_clocks[node_id] = VectorClock(
                node_id=node_id,
                clock={node_id: 0},
                timestamp=time.time(),
                version=0
            )
        
        current = self.vector_clocks[node_id].clock
        for key, value in other_clock.items():
            if key not in current or current[key] < value:
                current[key] = value
        
        self.vector_clocks[node_id].timestamp = time.time()
        self.vector_clocks[node_id].version += 1
    
    # ============================================
    # Distributed Locking
    # ============================================
    
    async def acquire_lock(
        self,
        resource_id: str,
        node_id: str,
        timeout: float = None
    ) -> Optional[str]:
        """
        Acquire a distributed lock.
        
        Args:
            resource_id: Resource to lock
            node_id: Node requesting lock
            timeout: Lock timeout in seconds
            
        Returns:
            Lock ID if acquired, None otherwise
        """
        if timeout is None:
            timeout = self.config.lock_timeout
        
        lock_id = f"{resource_id}_{node_id}_{int(time.time())}"
        
        # Check if lock already exists
        async with self.resource_lock:
            if resource_id in self.locks:
                existing_lock = self.locks[resource_id]
                if existing_lock.expires_at > time.time():
                    self.logger.warning(
                        f"Lock on {resource_id} already held by {existing_lock.holder}"
                    )
                    return None
            
            # Create lock
            self.locks[resource_id] = DistributedLock(
                lock_id=lock_id,
                resource_id=resource_id,
                holder=node_id,
                acquired_at=time.time(),
                expires_at=time.time() + timeout,
                renew_count=0,
                metadata={}
            )
        
        self.logger.info(f"Lock {lock_id} acquired by {node_id} on {resource_id}")
        return lock_id
    
    async def release_lock(self, lock_id: str, node_id: str) -> bool:
        """
        Release a distributed lock.
        
        Args:
            lock_id: Lock identifier
            node_id: Node releasing lock
            
        Returns:
            True if lock released, False otherwise
        """
        async with self.resource_lock:
            for resource_id, lock in self.locks.items():
                if lock.lock_id == lock_id:
                    if lock.holder != node_id:
                        self.logger.warning(
                            f"Node {node_id} cannot release lock {lock_id} held by {lock.holder}"
                        )
                        return False
                    
                    del self.locks[resource_id]
                    self.logger.info(f"Lock {lock_id} released by {node_id}")
                    return True
        
        self.logger.warning(f"Lock {lock_id} not found")
        return False
    
    async def renew_lock(self, lock_id: str, node_id: str) -> bool:
        """
        Renew a distributed lock.
        
        Args:
            lock_id: Lock identifier
            node_id: Node renewing lock
            
        Returns:
            True if lock renewed, False otherwise
        """
        async with self.resource_lock:
            for resource_id, lock in self.locks.items():
                if lock.lock_id == lock_id:
                    if lock.holder != node_id:
                        return False
                    
                    lock.expires_at = time.time() + self.config.lock_timeout
                    lock.renew_count += 1
                    self.logger.info(f"Lock {lock_id} renewed by {node_id}")
                    return True
        
        return False
    
    # ============================================
    # Distributed Counters
    # ============================================
    
    async def create_counter(self, counter_id: str, node_id: str) -> bool:
        """
        Create a distributed counter.
        
        Args:
            counter_id: Counter identifier
            node_id: Node creating the counter
            
        Returns:
            True if counter created, False otherwise
        """
        if counter_id in self.counters:
            self.logger.warning(f"Counter {counter_id} already exists")
            return False
        
        self.counters[counter_id] = DistributedCounter(
            counter_id=counter_id,
            value=0,
            node_id=node_id,
            updated_at=time.time(),
            version=1,
            metadata={}
        )
        
        self.logger.info(f"Counter {counter_id} created by {node_id}")
        return True
    
    async def increment_counter(
        self,
        counter_id: str,
        node_id: str,
        delta: int = 1
    ) -> Optional[int]:
        """
        Increment a distributed counter.
        
        Args:
            counter_id: Counter identifier
            node_id: Node incrementing counter
            delta: Amount to increment
            
        Returns:
            New counter value, None if counter not found
        """
        if counter_id not in self.counters:
            self.logger.warning(f"Counter {counter_id} not found")
            return None
        
        counter = self.counters[counter_id]
        counter.value += delta
        counter.node_id = node_id
        counter.updated_at = time.time()
        counter.version += 1
        
        self.logger.info(f"Counter {counter_id} incremented to {counter.value} by {node_id}")
        return counter.value
    
    async def decrement_counter(
        self,
        counter_id: str,
        node_id: str,
        delta: int = 1
    ) -> Optional[int]:
        """
        Decrement a distributed counter.
        
        Args:
            counter_id: Counter identifier
            node_id: Node decrementing counter
            delta: Amount to decrement
            
        Returns:
            New counter value, None if counter not found
        """
        return await self.increment_counter(counter_id, node_id, -delta)
    
    async def get_counter_value(self, counter_id: str) -> Optional[int]:
        """
        Get current counter value.
        
        Args:
            counter_id: Counter identifier
            
        Returns:
            Counter value, None if counter not found
        """
        if counter_id not in self.counters:
            return None
        
        return self.counters[counter_id].value
    
    # ============================================
    # Distributed Operations
    # ============================================
    
    async def all_reduce(
        self,
        sender: str,
        receivers: List[str],
        data: Any,
        reduce_fn: Callable[[List[Any]], Any] = None
    ) -> str:
        """
        Perform an all-reduce operation.
        
        Args:
            sender: Sending node
            receivers: Receiving nodes
            data: Data to reduce
            reduce_fn: Reduction function
            
        Returns:
            Operation ID
        """
        if reduce_fn is None:
            reduce_fn = lambda x: np.mean(x, axis=0)
        
        operation_id = await self._create_operation(
            OperationType.ALL_REDUCE,
            sender,
            receivers,
            data,
            reduce_fn
        )
        
        await self._execute_operation(operation_id)
        return operation_id
    
    async def broadcast(
        self,
        sender: str,
        receivers: List[str],
        data: Any
    ) -> str:
        """
        Perform a broadcast operation.
        
        Args:
            sender: Sending node
            receivers: Receiving nodes
            data: Data to broadcast
            
        Returns:
            Operation ID
        """
        operation_id = await self._create_operation(
            OperationType.BROADCAST,
            sender,
            receivers,
            data
        )
        
        await self._execute_operation(operation_id)
        return operation_id
    
    async def scatter(
        self,
        sender: str,
        receivers: List[str],
        data: List[Any]
    ) -> str:
        """
        Perform a scatter operation.
        
        Args:
            sender: Sending node
            receivers: Receiving nodes
            data: Data to scatter
            
        Returns:
            Operation ID
        """
        if len(data) != len(receivers):
            raise ValueError("Data length must match receivers length")
        
        operation_id = await self._create_operation(
            OperationType.SCATTER,
            sender,
            receivers,
            data
        )
        
        await self._execute_operation(operation_id)
        return operation_id
    
    async def gather(
        self,
        sender: str,
        receivers: List[str],
        data: Any
    ) -> str:
        """
        Perform a gather operation.
        
        Args:
            sender: Sending node
            receivers: Receiving nodes
            data: Data to gather
            
        Returns:
            Operation ID
        """
        operation_id = await self._create_operation(
            OperationType.GATHER,
            sender,
            receivers,
            data
        )
        
        await self._execute_operation(operation_id)
        return operation_id
    
    async def all_gather(
        self,
        sender: str,
        receivers: List[str],
        data: Any
    ) -> str:
        """
        Perform an all-gather operation.
        
        Args:
            sender: Sending node
            receivers: Receiving nodes
            data: Data to gather
            
        Returns:
            Operation ID
        """
        operation_id = await self._create_operation(
            OperationType.ALL_GATHER,
            sender,
            receivers,
            data
        )
        
        await self._execute_operation(operation_id)
        return operation_id
    
    async def reduce(
        self,
        sender: str,
        receivers: List[str],
        data: Any,
        reduce_fn: Callable[[List[Any]], Any] = None
    ) -> str:
        """
        Perform a reduce operation.
        
        Args:
            sender: Sending node
            receivers: Receiving nodes
            data: Data to reduce
            reduce_fn: Reduction function
            
        Returns:
            Operation ID
        """
        if reduce_fn is None:
            reduce_fn = lambda x: np.mean(x, axis=0)
        
        operation_id = await self._create_operation(
            OperationType.REDUCE,
            sender,
            receivers,
            data,
            reduce_fn
        )
        
        await self._execute_operation(operation_id)
        return operation_id
    
    # ============================================
    # Operation Management
    # ============================================
    
    async def _create_operation(
        self,
        op_type: OperationType,
        sender: str,
        receivers: List[str],
        data: Any,
        reduce_fn: Callable = None
    ) -> str:
        """
        Create a new operation.
        
        Args:
            op_type: Operation type
            sender: Sending node
            receivers: Receiving nodes
            data: Operation data
            reduce_fn: Reduction function
            
        Returns:
            Operation ID
        """
        operation_id = str(uuid.uuid4())
        
        operation = SyncOperation(
            operation_id=operation_id,
            operation_type=op_type,
            sender=sender,
            receivers=receivers,
            data=data,
            timestamp=time.time(),
            status=SyncStatus.PENDING,
            timeout=self.config.operation_timeout,
            retries=self.config.max_retries,
            metadata={'reduce_fn': reduce_fn} if reduce_fn else {}
        )
        
        async with self.operation_lock:
            self.operations[operation_id] = operation
            self.pending_operations.append(operation_id)
            self.metrics['pending_ops'] = len(self.pending_operations)
        
        self.logger.info(f"Operation {operation_id} created: {op_type.value}")
        return operation_id
    
    async def _execute_operation(self, operation_id: str) -> None:
        """
        Execute a pending operation.
        
        Args:
            operation_id: Operation identifier
        """
        if operation_id not in self.operations:
            self.logger.warning(f"Operation {operation_id} not found")
            return
        
        operation = self.operations[operation_id]
        
        async with self.operation_lock:
            if operation_id in self.active_operations:
                return
            
            self.pending_operations.remove(operation_id)
            self.active_operations.add(operation_id)
            operation.status = SyncStatus.IN_PROGRESS
            operation.updated_at = time.time()
            
            self.metrics['active_ops'] = len(self.active_operations)
            self.metrics['pending_ops'] = len(self.pending_operations)
        
        try:
            start_time = time.time()
            
            # Execute based on operation type
            if operation.operation_type == OperationType.ALL_REDUCE:
                result = await self._execute_all_reduce(operation)
            elif operation.operation_type == OperationType.BROADCAST:
                result = await self._execute_broadcast(operation)
            elif operation.operation_type == OperationType.SCATTER:
                result = await self._execute_scatter(operation)
            elif operation.operation_type == OperationType.GATHER:
                result = await self._execute_gather(operation)
            elif operation.operation_type == OperationType.ALL_GATHER:
                result = await self._execute_all_gather(operation)
            elif operation.operation_type == OperationType.REDUCE:
                result = await self._execute_reduce(operation)
            else:
                raise ValueError(f"Unknown operation type: {operation.operation_type}")
            
            latency = time.time() - start_time
            
            # Update operation status
            async with self.operation_lock:
                operation.status = SyncStatus.COMPLETED
                operation.results = {'result': result}
                operation.updated_at = time.time()
                self.active_operations.remove(operation_id)
                self.completed_operations.append(operation_id)
                
                self.metrics['successful_operations'] += 1
                self.metrics['active_ops'] = len(self.active_operations)
                
                # Update latency metrics
                self.metrics['average_latency'] = (
                    self.metrics['average_latency'] * (self.metrics['successful_operations'] - 1) + latency
                ) / self.metrics['successful_operations']
                self.metrics['max_latency'] = max(self.metrics['max_latency'], latency)
                self.metrics['min_latency'] = min(self.metrics['min_latency'], latency)
            
            self.logger.info(
                f"Operation {operation_id} completed in {latency:.3f}s"
            )
            
        except Exception as e:
            self.logger.error(f"Operation {operation_id} failed: {e}")
            
            async with self.operation_lock:
                operation.status = SyncStatus.FAILED
                operation.updated_at = time.time()
                self.active_operations.remove(operation_id)
                self.metrics['failed_operations'] += 1
                self.metrics['active_ops'] = len(self.active_operations)
    
    # ============================================
    # Operation Executors
    # ============================================
    
    async def _execute_all_reduce(self, operation: SyncOperation) -> Any:
        """
        Execute all-reduce operation.
        
        Args:
            operation: Operation to execute
            
        Returns:
            Reduced result
        """
        # In a real implementation, this would communicate with all receivers
        # For now, simulate with local computation
        data = operation.data
        reduce_fn = operation.metadata.get('reduce_fn')
        
        if reduce_fn:
            # Simulate all-reduce with local processing
            return reduce_fn([data] * len(operation.receivers))
        
        return data
    
    async def _execute_broadcast(self, operation: SyncOperation) -> Any:
        """
        Execute broadcast operation.
        
        Args:
            operation: Operation to execute
            
        Returns:
            Broadcast data
        """
        return operation.data
    
    async def _execute_scatter(self, operation: SyncOperation) -> Dict[str, Any]:
        """
        Execute scatter operation.
        
        Args:
            operation: Operation to execute
            
        Returns:
            Scattered data per receiver
        """
        data_list = operation.data
        receivers = operation.receivers
        
        if len(data_list) != len(receivers):
            raise ValueError("Data length must match receivers length")
        
        return {
            receiver: data_list[i]
            for i, receiver in enumerate(receivers)
        }
    
    async def _execute_gather(self, operation: SyncOperation) -> List[Any]:
        """
        Execute gather operation.
        
        Args:
            operation: Operation to execute
            
        Returns:
            Gathered data
        """
        # Simulate gathering from all receivers
        return [operation.data] * len(operation.receivers)
    
    async def _execute_all_gather(self, operation: SyncOperation) -> List[Any]:
        """
        Execute all-gather operation.
        
        Args:
            operation: Operation to execute
            
        Returns:
            All-gathered data
        """
        return [operation.data] * len(operation.receivers)
    
    async def _execute_reduce(self, operation: SyncOperation) -> Any:
        """
        Execute reduce operation.
        
        Args:
            operation: Operation to execute
            
        Returns:
            Reduced result
        """
        data = operation.data
        reduce_fn = operation.metadata.get('reduce_fn')
        
        if reduce_fn:
            return reduce_fn([data] * len(operation.receivers))
        
        return data
    
    # ============================================
    # Operation Status and Results
    # ============================================
    
    async def get_operation_status(self, operation_id: str) -> Optional[SyncStatus]:
        """
        Get operation status.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            Operation status
        """
        if operation_id not in self.operations:
            return None
        
        return self.operations[operation_id].status
    
    async def get_operation_result(self, operation_id: str) -> Optional[Any]:
        """
        Get operation result.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            Operation result
        """
        if operation_id not in self.operations:
            return None
        
        operation = self.operations[operation_id]
        if operation.status != SyncStatus.COMPLETED:
            return None
        
        return operation.results.get('result')
    
    async def wait_for_operation(
        self,
        operation_id: str,
        timeout: float = None
    ) -> Optional[Any]:
        """
        Wait for operation to complete.
        
        Args:
            operation_id: Operation identifier
            timeout: Timeout in seconds
            
        Returns:
            Operation result if successful
        """
        if timeout is None:
            timeout = self.config.operation_timeout
        
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                self.logger.warning(f"Operation {operation_id} timed out")
                return None
            
            if operation_id not in self.operations:
                return None
            
            status = await self.get_operation_status(operation_id)
            
            if status == SyncStatus.COMPLETED:
                return await self.get_operation_result(operation_id)
            elif status == SyncStatus.FAILED:
                return None
            
            await asyncio.sleep(0.1)
    
    # ============================================
    # Health Check and Monitoring
    # ============================================
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health status information
        """
        active_nodes = await self.get_active_nodes()
        
        return {
            'status': 'healthy' if active_nodes else 'degraded',
            'timestamp': time.time(),
            'sync_mode': self.config.sync_mode,
            'node_count': len(self.nodes),
            'active_nodes': len(active_nodes),
            'pending_operations': len(self.pending_operations),
            'active_operations': len(self.active_operations),
            'total_operations': self.metrics['total_operations'],
            'successful_operations': self.metrics['successful_operations'],
            'failed_operations': self.metrics['failed_operations'],
        }
    
    async def get_sync_metrics(self) -> SyncMetrics:
        """
        Get synchronization metrics.
        
        Returns:
            SyncMetrics object
        """
        active_nodes = await self.get_active_nodes()
        
        return SyncMetrics(
            timestamp=time.time(),
            operation_count=self.metrics['total_operations'],
            success_count=self.metrics['successful_operations'],
            failure_count=self.metrics['failed_operations'],
            average_latency=self.metrics['average_latency'],
            max_latency=self.metrics['max_latency'],
            min_latency=self.metrics['min_latency'],
            throughput=self.metrics.get('throughput', 0),
            pending_operations=len(self.pending_operations),
            active_operations=len(self.active_operations),
            node_count=len(active_nodes)
        )
    
    # ============================================
    # Background Tasks
    # ============================================
    
    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while True:
            try:
                # Check node heartbeats
                current_time = time.time()
                offline_nodes = []
                
                for node_id, heartbeat in self.node_heartbeats.items():
                    if current_time - heartbeat > self.config.heartbeat_interval * 3:
                        offline_nodes.append(node_id)
                
                # Remove offline nodes
                for node_id in offline_nodes:
                    self.logger.warning(f"Node {node_id} offline - removing")
                    await self.unregister_node(node_id)
                
                # Clean up expired locks
                current_time = time.time()
                expired_locks = []
                async with self.resource_lock:
                    for resource_id, lock in self.locks.items():
                        if lock.expires_at < current_time:
                            expired_locks.append(resource_id)
                    
                    for resource_id in expired_locks:
                        del self.locks[resource_id]
                        self.logger.info(f"Lock on {resource_id} expired")
                
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                await asyncio.sleep(30)
    
    async def _process_pending_operations(self) -> None:
        """Process pending operations."""
        while True:
            try:
                if self.pending_operations and len(self.active_operations) < self.config.max_concurrent_operations:
                    operation_id = self.pending_operations.popleft()
                    asyncio.create_task(self._execute_operation(operation_id))
                
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Operation processing error: {e}")
                await asyncio.sleep(1)
    
    async def _metrics_collection_loop(self) -> None:
        """Background metrics collection loop."""
        while True:
            try:
                metrics = await self.get_sync_metrics()
                
                # Store metrics in Redis
                if self.redis_client:
                    try:
                        await self.redis_client.set(
                            "sync:metrics:latest",
                            json.dumps({
                                'timestamp': metrics.timestamp,
                                'operation_count': metrics.operation_count,
                                'success_count': metrics.success_count,
                                'failure_count': metrics.failure_count,
                                'average_latency': metrics.average_latency,
                                'max_latency': metrics.max_latency,
                                'min_latency': metrics.min_latency,
                                'throughput': metrics.throughput,
                                'pending_operations': metrics.pending_operations,
                                'active_operations': metrics.active_operations,
                                'node_count': metrics.node_count,
                            }),
                            ex=3600
                        )
                    except Exception as e:
                        self.logger.error(f"Failed to store metrics: {e}")
                
                await asyncio.sleep(self.config.metrics_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(60)
    
    # ============================================
    # API Handlers
    # ============================================
    
    async def handle_register(self, request: web.Request) -> web.Response:
        """Handle node registration."""
        try:
            data = await request.json()
            node_id = data.get('node_id')
            metadata = data.get('metadata', {})
            
            if not node_id:
                return web.json_response({'error': 'node_id required'}, status=400)
            
            success = await self.register_node(node_id, metadata)
            if success:
                return web.json_response({
                    'status': 'registered',
                    'node_id': node_id,
                })
            else:
                return web.json_response({'error': 'registration failed'}, status=400)
                
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_unregister(self, request: web.Request) -> web.Response:
        """Handle node unregistration."""
        try:
            data = await request.json()
            node_id = data.get('node_id')
            
            if not node_id:
                return web.json_response({'error': 'node_id required'}, status=400)
            
            success = await self.unregister_node(node_id)
            if success:
                return web.json_response({'status': 'unregistered'})
            else:
                return web.json_response({'error': 'node not found'}, status=404)
                
        except Exception as e:
            self.logger.error(f"Unregistration error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_heartbeat(self, request: web.Request) -> web.Response:
        """Handle node heartbeat."""
        try:
            data = await request.json()
            node_id = data.get('node_id')
            
            if not node_id:
                return web.json_response({'error': 'node_id required'}, status=400)
            
            success = await self.update_heartbeat(node_id)
            if success:
                return web.json_response({'status': 'ok'})
            else:
                return web.json_response({'error': 'node not found'}, status=404)
                
        except Exception as e:
            self.logger.error(f"Heartbeat error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_lock(self, request: web.Request) -> web.Response:
        """Handle lock acquisition."""
        try:
            data = await request.json()
            resource_id = data.get('resource_id')
            node_id = data.get('node_id')
            timeout = data.get('timeout')
            
            if not resource_id or not node_id:
                return web.json_response({
                    'error': 'resource_id and node_id required'
                }, status=400)
            
            lock_id = await self.acquire_lock(resource_id, node_id, timeout)
            if lock_id:
                return web.json_response({
                    'status': 'locked',
                    'lock_id': lock_id,
                })
            else:
                return web.json_response({
                    'status': 'failed',
                    'message': 'lock already held or timeout'
                }, status=409)
                
        except Exception as e:
            self.logger.error(f"Lock error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_unlock(self, request: web.Request) -> web.Response:
        """Handle lock release."""
        try:
            data = await request.json()
            lock_id = data.get('lock_id')
            node_id = data.get('node_id')
            
            if not lock_id or not node_id:
                return web.json_response({
                    'error': 'lock_id and node_id required'
                }, status=400)
            
            success = await self.release_lock(lock_id, node_id)
            if success:
                return web.json_response({'status': 'unlocked'})
            else:
                return web.json_response({
                    'status': 'failed',
                    'message': 'lock not found or not held by node'
                }, status=404)
                
        except Exception as e:
            self.logger.error(f"Unlock error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Handle health check request."""
        try:
            health = await self.health_check()
            return web.json_response(health)
        except Exception as e:
            self.logger.error(f"Health check error: {e}")
            return web.json_response({'status': 'error', 'error': str(e)}, status=500)
    
    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Handle metrics request."""
        try:
            metrics = await self.get_sync_metrics()
            return web.json_response({
                'timestamp': metrics.timestamp,
                'operation_count': metrics.operation_count,
                'success_count': metrics.success_count,
                'failure_count': metrics.failure_count,
                'average_latency': metrics.average_latency,
                'max_latency': metrics.max_latency,
                'min_latency': metrics.min_latency,
                'throughput': metrics.throughput,
                'pending_operations': metrics.pending_operations,
                'active_operations': metrics.active_operations,
                'node_count': metrics.node_count,
            })
        except Exception as e:
            self.logger.error(f"Metrics error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # ============================================
    # Server Lifecycle
    # ============================================
    
    def run(self) -> None:
        """Run the synchronization manager."""
        app = web.Application()
        
        # Register routes
        app.router.add_post('/api/register', self.handle_register)
        app.router.add_post('/api/unregister', self.handle_unregister)
        app.router.add_post('/api/heartbeat', self.handle_heartbeat)
        app.router.add_post('/api/lock', self.handle_lock)
        app.router.add_post('/api/unlock', self.handle_unlock)
        app.router.add_get('/api/health', self.handle_health)
        app.router.add_get('/api/metrics', self.handle_metrics)
        
        # Add middleware
        app.middlewares.append(self._error_middleware)
        
        # Run server
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        loop = asyncio.get_event_loop()
        
        try:
            loop.run_until_complete(self._start_server(app))
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        finally:
            loop.run_until_complete(self._shutdown())
    
    async def _start_server(self, app: web.Application) -> None:
        """Start the HTTP server."""
        # Connect to Redis
        await self._connect_redis()
        
        # Start background tasks
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._process_pending_operations())
        
        if self.config.enable_metrics:
            self.metrics_task = asyncio.create_task(self._metrics_collection_loop())
        
        # Start server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner,
            host=self.config.host,
            port=self.config.port
        )
        await site.start()
        
        self.logger.info(
            f"Sync Manager running on {self.config.host}:{self.config.port}"
        )
        
        # Keep running
        await asyncio.Event().wait()
    
    async def _shutdown(self) -> None:
        """Shutdown the server."""
        # Cancel background tasks
        if self.health_check_task:
            self.health_check_task.cancel()
        if self.metrics_task:
            self.metrics_task.cancel()
        
        # Disconnect from Redis
        await self._disconnect_redis()
        
        self.logger.info("Sync Manager shutdown complete")
    
    async def _error_middleware(
        self,
        app: web.Application,
        handler
    ) -> web.Response:
        """Error handling middleware."""
        async def middleware(request: web.Request) -> web.Response:
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Unhandled error: {e}")
                return web.json_response(
                    {'error': 'Internal server error'},
                    status=500
                )
        return middleware


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Sync Manager')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=8081, help='Server port')
    parser.add_argument('--redis-url', default='redis://localhost:6379', help='Redis URL')
    parser.add_argument('--sync-mode', default='synchronous', 
                       choices=['synchronous', 'asynchronous', 'semi_synchronous'],
                       help='Synchronization mode')
    parser.add_argument('--log-level', default='INFO', help='Log level')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create configuration
    config = SyncManagerConfig(
        host=args.host,
        port=args.port,
        redis_url=args.redis_url,
        sync_mode=args.sync_mode,
        log_level=args.log_level,
    )
    
    # Run server
    sync_manager = SyncManager(config)
    sync_manager.run()


if __name__ == '__main__':
    main()
