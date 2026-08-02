# trading/bots/hedge_bot/hedge_bot_data_replication.py

import asyncio
import logging
import time
import json
import hashlib
import pickle
import zlib
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque
import threading
import queue

logger = logging.getLogger(__name__)


class ReplicationMode(str, Enum):
    MASTER = "master"
    SLAVE = "slave"
    MASTER_SLAVE = "master_slave"
    MULTI_MASTER = "multi_master"
    PEER_TO_PEER = "peer_to_peer"
    PUBSUB = "pubsub"
    BATCH = "batch"
    STREAMING = "streaming"
    SNAPSHOT = "snapshot"
    INCREMENTAL = "incremental"
    FULL = "full"


class ReplicationStrategy(str, Enum):
    ASYNC = "async"
    SYNC = "sync"
    SEMI_SYNC = "semi_sync"
    EVENTUAL = "eventual"
    STRONG = "strong"
    READ_YOUR_WRITES = "read_your_writes"
    MONOTONIC = "monotonic"
    BOUNDED_STALENESS = "bounded_staleness"


class ReplicationStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConflictResolution(str, Enum):
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MERGE = "merge"
    CUSTOM = "custom"
    MANUAL = "manual"
    VERSION_VECTORS = "version_vectors"
    CRDT = "crdt"


@dataclass
class ReplicationNode:
    id: str
    name: str
    host: str
    port: int
    role: ReplicationMode
    status: ReplicationStatus
    last_heartbeat: float
    latency: float
    version: str
    capabilities: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplicationConfig:
    mode: ReplicationMode
    strategy: ReplicationStrategy
    conflict_resolution: ConflictResolution
    batch_size: int = 1000
    batch_timeout: float = 1.0
    heartbeat_interval: float = 5.0
    sync_interval: float = 30.0
    retry_interval: float = 1.0
    max_retries: int = 5
    timeout: float = 30.0
    compression: bool = True
    encryption: bool = True
    signature: bool = True
    versioning: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplicationMessage:
    id: str
    type: str
    source: str
    target: str
    data: Any
    timestamp: float
    version: int
    checksum: str
    signature: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    expires_at: Optional[float] = None


@dataclass
class ReplicationBatch:
    id: str
    source: str
    target: str
    messages: List[ReplicationMessage]
    timestamp: float
    size: int
    compressed: bool
    encrypted: bool
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplicationSnapshot:
    id: str
    source: str
    data: Any
    timestamp: float
    size: int
    version: str
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplicationStatusReport:
    node_id: str
    status: ReplicationStatus
    last_sync: float
    next_sync: float
    messages_sent: int
    messages_received: int
    messages_pending: int
    errors: int
    latency: float
    throughput: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataReplicationManager:
    
    def __init__(self, config: Optional[ReplicationConfig] = None):
        self.config = config or ReplicationConfig(
            mode=ReplicationMode.MASTER_SLAVE,
            strategy=ReplicationStrategy.ASYNC,
            conflict_resolution=ConflictResolution.LAST_WRITE_WINS
        )
        self._lock = asyncio.Lock()
        self._nodes: Dict[str, ReplicationNode] = {}
        self._local_node: Optional[ReplicationNode] = None
        self._messages: Dict[str, ReplicationMessage] = {}
        self._batches: Dict[str, ReplicationBatch] = {}
        self._snapshots: Dict[str, ReplicationSnapshot] = {}
        self._pending_messages: Dict[str, List[ReplicationMessage]] = defaultdict(list)
        self._processed_messages: Set[str] = set()
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._replication_tasks: Dict[str, asyncio.Task] = {}
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._sync_tasks: Dict[str, asyncio.Task] = {}
        self._handlers: Dict[str, Callable] = {}
        self._conflict_handlers: Dict[str, Callable] = {}
        self._observers: List[Callable] = []
        self._stats = defaultdict(int)
        self._last_heartbeat = 0.0
        self._version_vectors: Dict[str, int] = defaultdict(int)
        
        self._initialize_handlers()

    def _initialize_handlers(self) -> None:
        self.register_handler("data", self._handle_data)
        self.register_handler("heartbeat", self._handle_heartbeat)
        self.register_handler("sync", self._handle_sync)
        self.register_handler("snapshot", self._handle_snapshot)
        self.register_handler("batch", self._handle_batch)
        self.register_handler("conflict", self._handle_conflict)

    def register_handler(self, message_type: str, handler: Callable) -> None:
        self._handlers[message_type] = handler

    def register_conflict_handler(self, conflict_type: str, handler: Callable) -> None:
        self._conflict_handlers[conflict_type] = handler

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def start(self, node: ReplicationNode) -> None:
        async with self._lock:
            if self._running:
                return
            
            self._local_node = node
            self._nodes[node.id] = node
            self._running = True
            
            self._message_queue = asyncio.Queue()
            
            for node_id, node_data in self._nodes.items():
                if node_data.id != self._local_node.id:
                    await self._connect_node(node_data)
            
            self._heartbeat_tasks["main"] = asyncio.create_task(self._heartbeat_loop())
            self._sync_tasks["main"] = asyncio.create_task(self._sync_loop())
            
            logger.info(f"Replication manager started as {node.role.value}")

    async def stop(self) -> None:
        async with self._lock:
            self._running = False
            
            for task in list(self._replication_tasks.values()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._replication_tasks.clear()
            
            for task in list(self._heartbeat_tasks.values()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._heartbeat_tasks.clear()
            
            for task in list(self._sync_tasks.values()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._sync_tasks.clear()
            
            logger.info("Replication manager stopped")

    async def add_node(self, node: ReplicationNode) -> None:
        async with self._lock:
            self._nodes[node.id] = node
            
            if self._running:
                await self._connect_node(node)
                await self._notify_observers("node_added", node)

    async def remove_node(self, node_id: str) -> bool:
        async with self._lock:
            if node_id not in self._nodes:
                return False
            
            if node_id in self._replication_tasks:
                self._replication_tasks[node_id].cancel()
                try:
                    await self._replication_tasks[node_id]
                except asyncio.CancelledError:
                    pass
                del self._replication_tasks[node_id]
            
            if node_id in self._heartbeat_tasks:
                self._heartbeat_tasks[node_id].cancel()
                try:
                    await self._heartbeat_tasks[node_id]
                except asyncio.CancelledError:
                    pass
                del self._heartbeat_tasks[node_id]
            
            if node_id in self._sync_tasks:
                self._sync_tasks[node_id].cancel()
                try:
                    await self._sync_tasks[node_id]
                except asyncio.CancelledError:
                    pass
                del self._sync_tasks[node_id]
            
            del self._nodes[node_id]
            
            await self._notify_observers("node_removed", node_id)
            return True

    async def _connect_node(self, node: ReplicationNode) -> None:
        logger.info(f"Connecting to node: {node.id}")
        
        task = asyncio.create_task(self._replication_loop(node))
        self._replication_tasks[node.id] = task
        
        heartbeat_task = asyncio.create_task(self._node_heartbeat_loop(node))
        self._heartbeat_tasks[node.id] = heartbeat_task
        
        sync_task = asyncio.create_task(self._node_sync_loop(node))
        self._sync_tasks[node.id] = sync_task

    async def replicate(
        self,
        data: Any,
        target_nodes: Optional[List[str]] = None,
        message_type: str = "data",
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> List[str]:
        async with self._lock:
            if not self._running:
                raise RuntimeError("Replication manager not running")
            
            if self.config.mode == ReplicationMode.MASTER:
                if self._local_node.role != ReplicationMode.MASTER:
                    if not force:
                        raise RuntimeError("Only master can replicate")
            
            targets = target_nodes or [n for n in self._nodes.keys() if n != self._local_node.id]
            
            message = await self._create_message(
                message_type=message_type,
                data=data,
                targets=targets,
                metadata=metadata
            )
            
            self._messages[message.id] = message
            
            for target in targets:
                self._pending_messages[target].append(message)
            
            for target in targets:
                await self._notify_observers("message_queued", target, message)
            
            self._stats['messages_queued'] += 1
            return targets

    async def _create_message(
        self,
        message_type: str,
        data: Any,
        targets: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReplicationMessage:
        message_id = hashlib.md5(f"{time.time()}_{id(data)}_{message_type}".encode()).hexdigest()
        
        serialized = self._serialize(data)
        checksum = hashlib.sha256(serialized).hexdigest()
        
        if self.config.signature:
            signature = self._sign(serialized)
        else:
            signature = None
        
        version = self._version_vectors[self._local_node.id] + 1
        self._version_vectors[self._local_node.id] = version
        
        return ReplicationMessage(
            id=message_id,
            type=message_type,
            source=self._local_node.id,
            target=",".join(targets),
            data=data,
            timestamp=time.time(),
            version=version,
            checksum=checksum,
            signature=signature,
            metadata=metadata or {},
            retry_count=0,
            expires_at=time.time() + 300
        )

    async def _replication_loop(self, node: ReplicationNode) -> None:
        while self._running:
            try:
                if node.id in self._pending_messages and self._pending_messages[node.id]:
                    messages = self._pending_messages[node.id][:self.config.batch_size]
                    
                    if len(messages) == 1:
                        await self._send_message(node, messages[0])
                    else:
                        await self._send_batch(node, messages)
                    
                    for msg in messages:
                        self._pending_messages[node.id].remove(msg)
                        self._processed_messages.add(msg.id)
                    
                    self._stats['messages_sent'] += len(messages)
                    
                await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Replication loop error for {node.id}: {e}")
                await asyncio.sleep(self.config.retry_interval)

    async def _send_message(self, node: ReplicationNode, message: ReplicationMessage) -> bool:
        try:
            serialized = self._serialize(message)
            
            if self.config.compression:
                serialized = zlib.compress(serialized)
            
            if self.config.encryption:
                serialized = self._encrypt(serialized)
            
            if self.config.signature:
                serialized = serialized + b"|" + message.signature.encode()
            
            await self._notify_observers("message_sent", node.id, message.id)
            
            self._stats['bytes_sent'] += len(serialized)
            self._stats['messages_sent'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending message to {node.id}: {e}")
            message.retry_count += 1
            
            if message.retry_count >= self.config.max_retries:
                self._stats['messages_failed'] += 1
                await self._notify_observers("message_failed", node.id, message.id)
                return False
            else:
                self._pending_messages[node.id].append(message)
                return False

    async def _send_batch(self, node: ReplicationNode, messages: List[ReplicationMessage]) -> bool:
        try:
            batch = await self._create_batch(node.id, messages)
            
            serialized = self._serialize(batch)
            
            if self.config.compression:
                serialized = zlib.compress(serialized)
            
            if self.config.encryption:
                serialized = self._encrypt(serialized)
            
            await self._notify_observers("batch_sent", node.id, batch.id)
            
            self._stats['batches_sent'] += 1
            self._stats['bytes_sent'] += len(serialized)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending batch to {node.id}: {e}")
            return False

    async def _create_batch(
        self,
        target: str,
        messages: List[ReplicationMessage]
    ) -> ReplicationBatch:
        batch_id = hashlib.md5(f"{time.time()}_{target}_{len(messages)}".encode()).hexdigest()
        
        serialized = self._serialize(messages)
        checksum = hashlib.sha256(serialized).hexdigest()
        
        batch = ReplicationBatch(
            id=batch_id,
            source=self._local_node.id,
            target=target,
            messages=messages,
            timestamp=time.time(),
            size=len(serialized),
            compressed=self.config.compression,
            encrypted=self.config.encryption,
            checksum=checksum
        )
        
        self._batches[batch_id] = batch
        return batch

    async def _node_heartbeat_loop(self, node: ReplicationNode) -> None:
        while self._running:
            try:
                await self._send_heartbeat(node)
                await asyncio.sleep(self.config.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error for {node.id}: {e}")
                await asyncio.sleep(self.config.retry_interval)

    async def _send_heartbeat(self, node: ReplicationNode) -> None:
        heartbeat = {
            "node_id": self._local_node.id,
            "timestamp": time.time(),
            "status": "online",
            "stats": dict(self._stats),
            "version": self._version_vectors[self._local_node.id]
        }
        
        await self.replicate(
            data=heartbeat,
            target_nodes=[node.id],
            message_type="heartbeat"
        )

    async def _node_sync_loop(self, node: ReplicationNode) -> None:
        while self._running:
            try:
                if self.config.mode in [ReplicationMode.MASTER_SLAVE, ReplicationMode.SLAVE]:
                    if self._local_node.role == ReplicationMode.SLAVE:
                        await self._sync_from_master(node)
                    elif self._local_node.role == ReplicationMode.MASTER:
                        await self._sync_to_slaves(node)
                elif self.config.mode == ReplicationMode.MULTI_MASTER:
                    await self._sync_multi_master(node)
                elif self.config.mode == ReplicationMode.PEER_TO_PEER:
                    await self._sync_peer_to_peer(node)
                
                await asyncio.sleep(self.config.sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync error for {node.id}: {e}")
                await asyncio.sleep(self.config.retry_interval)

    async def _sync_from_master(self, node: ReplicationNode) -> None:
        if node.role != ReplicationMode.MASTER:
            return
        
        snapshot = await self._request_snapshot(node.id)
        if snapshot:
            await self._apply_snapshot(snapshot)

    async def _sync_to_slaves(self, node: ReplicationNode) -> None:
        if node.role != ReplicationMode.SLAVE:
            return
        
        pending = self._pending_messages.get(node.id, [])
        if pending:
            await self._send_batch(node, pending)

    async def _sync_multi_master(self, node: ReplicationNode) -> None:
        if node.id == self._local_node.id:
            return
        
        version = self._version_vectors.get(node.id, 0)
        
        if version < self._version_vectors.get(self._local_node.id, 0):
            await self._send_missing_messages(node, version)

    async def _sync_peer_to_peer(self, node: ReplicationNode) -> None:
        if node.id == self._local_node.id:
            return
        
        await self._exchange_updates(node)

    async def _send_missing_messages(self, node: ReplicationNode, from_version: int) -> None:
        missing_messages = [
            msg for msg in self._messages.values()
            if msg.version > from_version and node.id in msg.target
        ]
        
        if missing_messages:
            await self._send_batch(node, missing_messages)

    async def _exchange_updates(self, node: ReplicationNode) -> None:
        my_version = self._version_vectors.get(self._local_node.id, 0)
        their_version = self._version_vectors.get(node.id, 0)
        
        if my_version > their_version:
            await self._send_missing_messages(node, their_version)
        elif their_version > my_version:
            await self._request_missing_messages(node, my_version)

    async def _request_snapshot(self, node_id: str) -> Optional[ReplicationSnapshot]:
        request = {
            "type": "snapshot_request",
            "source": self._local_node.id,
            "timestamp": time.time()
        }
        
        await self.replicate(
            data=request,
            target_nodes=[node_id],
            message_type="snapshot"
        )
        
        return None

    async def _apply_snapshot(self, snapshot: ReplicationSnapshot) -> None:
        await self._notify_observers("snapshot_applied", snapshot)
        self._snapshots[snapshot.id] = snapshot

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                for node in self._nodes.values():
                    if node.id != self._local_node.id:
                        node.last_heartbeat = time.time()
                        node.status = ReplicationStatus.RUNNING
                
                await self._notify_observers("heartbeat", self._local_node.id)
                await asyncio.sleep(self.config.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(self.config.retry_interval)

    async def _sync_loop(self) -> None:
        while self._running:
            try:
                await self._check_node_health()
                await self._process_pending_messages()
                await self._resolve_conflicts()
                await self._cleanup_old_messages()
                
                await asyncio.sleep(self.config.sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(self.config.retry_interval)

    async def _check_node_health(self) -> None:
        now = time.time()
        for node_id, node in self._nodes.items():
            if node_id != self._local_node.id:
                if now - node.last_heartbeat > self.config.heartbeat_interval * 3:
                    node.status = ReplicationStatus.ERROR
                    await self._notify_observers("node_error", node_id)

    async def _process_pending_messages(self) -> None:
        for node_id, messages in self._pending_messages.items():
            if messages and len(messages) >= self.config.batch_size:
                await self._send_batch(self._nodes[node_id], messages[:self.config.batch_size])
                self._pending_messages[node_id] = messages[self.config.batch_size:]

    async def _resolve_conflicts(self) -> None:
        if self.config.conflict_resolution == ConflictResolution.CUSTOM:
            for handler in self._conflict_handlers.values():
                await handler()

    async def _cleanup_old_messages(self) -> None:
        now = time.time()
        to_remove = [
            msg_id for msg_id, msg in self._messages.items()
            if msg.expires_at and msg.expires_at < now
        ]
        
        for msg_id in to_remove:
            del self._messages[msg_id]
        
        self._stats['messages_cleaned'] += len(to_remove)

    async def _handle_data(self, message: ReplicationMessage) -> None:
        await self._notify_observers("data_received", message)
        self._stats['data_received'] += 1

    async def _handle_heartbeat(self, message: ReplicationMessage) -> None:
        if message.source in self._nodes:
            self._nodes[message.source].last_heartbeat = time.time()
            self._nodes[message.source].status = ReplicationStatus.RUNNING
        self._stats['heartbeats_received'] += 1

    async def _handle_sync(self, message: ReplicationMessage) -> None:
        await self._notify_observers("sync_requested", message)
        self._stats['sync_requests'] += 1

    async def _handle_snapshot(self, message: ReplicationMessage) -> None:
        snapshot = message.data
        await self._apply_snapshot(snapshot)
        self._stats['snapshots_received'] += 1

    async def _handle_batch(self, message: ReplicationMessage) -> None:
        batch = message.data
        await self._process_batch(batch)
        self._stats['batches_received'] += 1

    async def _handle_conflict(self, message: ReplicationMessage) -> None:
        self._stats['conflicts_detected'] += 1
        
        if self.config.conflict_resolution == ConflictResolution.LAST_WRITE_WINS:
            existing = self._messages.get(message.id)
            if existing and existing.timestamp > message.timestamp:
                return
            self._messages[message.id] = message
            
        elif self.config.conflict_resolution == ConflictResolution.MERGE:
            await self._merge_data(message)

    async def _process_batch(self, batch: ReplicationBatch) -> None:
        for message in batch.messages:
            await self._process_message(message)
        
        self._stats['batch_messages_processed'] += len(batch.messages)

    async def _process_message(self, message: ReplicationMessage) -> None:
        if message.id in self._processed_messages:
            return
        
        if message.type in self._handlers:
            await self._handlers[message.type](message)
        
        self._processed_messages.add(message.id)
        self._stats['messages_received'] += 1

    async def _merge_data(self, message: ReplicationMessage) -> None:
        existing = self._messages.get(message.id)
        if existing:
            merged = await self._merge(existing.data, message.data)
            message.data = merged
        
        self._messages[message.id] = message

    async def _merge(self, data1: Any, data2: Any) -> Any:
        if isinstance(data1, dict) and isinstance(data2, dict):
            merged = data1.copy()
            for key, value in data2.items():
                if key in merged:
                    if isinstance(value, dict):
                        merged[key] = await self._merge(merged[key], value)
                    else:
                        merged[key] = value
                else:
                    merged[key] = value
            return merged
        elif isinstance(data1, list) and isinstance(data2, list):
            return list(set(data1 + data2))
        else:
            return data2

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def _serialize(self, data: Any) -> bytes:
        try:
            return pickle.dumps(data)
        except:
            return json.dumps(data, default=str).encode()

    def _deserialize(self, data: bytes) -> Any:
        try:
            return pickle.loads(data)
        except:
            return json.loads(data.decode())

    def _encrypt(self, data: bytes) -> bytes:
        return base64.b64encode(data)

    def _decrypt(self, data: bytes) -> bytes:
        return base64.b64decode(data)

    def _sign(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    async def get_status(self) -> ReplicationStatusReport:
        return ReplicationStatusReport(
            node_id=self._local_node.id if self._local_node else "",
            status=ReplicationStatus.RUNNING if self._running else ReplicationStatus.IDLE,
            last_sync=self._last_heartbeat,
            next_sync=self._last_heartbeat + self.config.sync_interval,
            messages_sent=self._stats['messages_sent'],
            messages_received=self._stats['messages_received'],
            messages_pending=sum(len(v) for v in self._pending_messages.values()),
            errors=self._stats['messages_failed'],
            latency=0.0,
            throughput=self._stats['bytes_sent'] / max(1, time.time() - self._last_heartbeat),
            metadata={
                "nodes": len(self._nodes),
                "messages": len(self._messages),
                "batches": len(self._batches),
                "snapshots": len(self._snapshots)
            }
        )

    async def get_nodes(self) -> List[ReplicationNode]:
        return list(self._nodes.values())

    async def get_pending_messages(self, node_id: str) -> List[ReplicationMessage]:
        return self._pending_messages.get(node_id, [])

    async def get_processed_messages(self) -> List[str]:
        return list(self._processed_messages)

    async def force_sync(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        
        await self._sync_loop()
        return True

    async def take_snapshot(self, node_id: str) -> Optional[ReplicationSnapshot]:
        data = await self._export_data()
        
        snapshot = ReplicationSnapshot(
            id=hashlib.md5(f"{time.time()}_{node_id}".encode()).hexdigest(),
            source=self._local_node.id,
            data=data,
            timestamp=time.time(),
            size=len(str(data)),
            version="1.0.0",
            checksum=hashlib.sha256(str(data).encode()).hexdigest()
        )
        
        self._snapshots[snapshot.id] = snapshot
        return snapshot

    async def _export_data(self) -> Dict[str, Any]:
        return {
            "messages": self._messages,
            "version_vectors": dict(self._version_vectors),
            "timestamp": time.time()
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "nodes": len(self._nodes),
            "messages": len(self._messages),
            "pending_messages": sum(len(v) for v in self._pending_messages.values()),
            "processed_messages": len(self._processed_messages),
            "batches": len(self._batches),
            "snapshots": len(self._snapshots),
            "version_vectors": dict(self._version_vectors),
            "messages_sent": self._stats['messages_sent'],
            "messages_received": self._stats['messages_received'],
            "messages_failed": self._stats['messages_failed'],
            "messages_cleaned": self._stats['messages_cleaned'],
            "batches_sent": self._stats['batches_sent'],
            "batches_received": self._stats['batches_received'],
            "bytes_sent": self._stats['bytes_sent'],
            "bytes_received": self._stats['bytes_received'],
            "heartbeats_received": self._stats['heartbeats_received'],
            "conflicts_detected": self._stats['conflicts_detected']
        }


__all__ = [
    "ReplicationMode",
    "ReplicationStrategy",
    "ReplicationStatus",
    "ConflictResolution",
    "ReplicationNode",
    "ReplicationConfig",
    "ReplicationMessage",
    "ReplicationBatch",
    "ReplicationSnapshot",
    "ReplicationStatusReport",
    "DataReplicationManager"
]
