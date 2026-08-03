# trading/bots/hedge_bot/hedge_bot_data_stream.py

import asyncio
import logging
import time
import json
import hashlib
import zlib
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class StreamType(str, Enum):
    REAL_TIME = "realtime"
    BATCH = "batch"
    MICRO_BATCH = "micro_batch"
    CONTINUOUS = "continuous"
    EVENT_DRIVEN = "event_driven"
    SCHEDULED = "scheduled"
    PUSH = "push"
    PULL = "pull"


class StreamMode(str, Enum):
    PUBLISH = "publish"
    SUBSCRIBE = "subscribe"
    PUB_SUB = "pubsub"
    REQUEST_RESPONSE = "request_response"
    PIPELINE = "pipeline"


class StreamStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    COMPLETED = "completed"


@dataclass
class StreamConfig:
    id: str
    name: str
    type: StreamType
    mode: StreamMode
    source: str
    destination: Optional[str] = None
    batch_size: int = 1000
    batch_timeout: float = 1.0
    buffer_size: int = 10000
    max_retries: int = 3
    retry_delay: float = 1.0
    compression: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamMessage:
    id: str
    stream_id: str
    data: Any
    timestamp: float
    sequence_number: int
    partition_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamBatch:
    id: str
    stream_id: str
    messages: List[StreamMessage]
    size: int
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamMetrics:
    stream_id: str
    messages_published: int
    messages_subscribed: int
    messages_processed: int
    messages_failed: int
    bytes_published: int
    bytes_subscribed: int
    throughput: float
    latency_avg: float
    latency_max: float
    timestamp: float = field(default_factory=time.time)


class DataStreamManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._streams: Dict[str, StreamConfig] = {}
        self._messages: Dict[str, StreamMessage] = {}
        self._batches: Dict[str, StreamBatch] = {}
        self._metrics: Dict[str, StreamMetrics] = {}
        self._buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._publishers: Dict[str, Callable] = {}
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._observers: List[Callable] = []
        self._running = False
        self._processors: Dict[str, List[Callable]] = defaultdict(list)
        self._filter_functions: Dict[str, List[Callable]] = defaultdict(list)
        self._transform_functions: Dict[str, List[Callable]] = defaultdict(list)
        self._batch_tasks: Dict[str, asyncio.Task] = {}
        self._flush_tasks: Dict[str, asyncio.Task] = {}
        
        self._initialize_default_streams()

    def _initialize_default_streams(self) -> None:
        default_streams = [
            StreamConfig(
                id="trading_data",
                name="Trading Data Stream",
                type=StreamType.REAL_TIME,
                mode=StreamMode.PUB_SUB,
                source="market_data",
                destination="trading_engine"
            ),
            StreamConfig(
                id="order_updates",
                name="Order Updates Stream",
                type=StreamType.EVENT_DRIVEN,
                mode=StreamMode.PUB_SUB,
                source="order_engine",
                destination="position_manager"
            ),
            StreamConfig(
                id="risk_metrics",
                name="Risk Metrics Stream",
                type=StreamType.CONTINUOUS,
                mode=StreamMode.PUB_SUB,
                source="risk_engine",
                destination="monitoring"
            )
        ]
        
        for stream in default_streams:
            self._streams[stream.id] = stream

    def register_publisher(self, stream_id: str, publisher: Callable) -> None:
        self._publishers[stream_id] = publisher

    def register_subscriber(self, stream_id: str, subscriber: Callable) -> None:
        self._subscribers[stream_id].append(subscriber)

    def register_processor(self, stream_id: str, processor: Callable) -> None:
        self._processors[stream_id].append(processor)

    def register_filter(self, stream_id: str, filter_func: Callable) -> None:
        self._filter_functions[stream_id].append(filter_func)

    def register_transform(self, stream_id: str, transform_func: Callable) -> None:
        self._transform_functions[stream_id].append(transform_func)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_stream(
        self,
        name: str,
        type: StreamType,
        mode: StreamMode,
        source: str,
        destination: Optional[str] = None,
        batch_size: int = 1000,
        batch_timeout: float = 1.0,
        buffer_size: int = 10000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        compression: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StreamConfig:
        async with self._lock:
            stream_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            stream = StreamConfig(
                id=stream_id,
                name=name,
                type=type,
                mode=mode,
                source=source,
                destination=destination,
                batch_size=batch_size,
                batch_timeout=batch_timeout,
                buffer_size=buffer_size,
                max_retries=max_retries,
                retry_delay=retry_delay,
                compression=compression,
                metadata=metadata or {}
            )
            
            self._streams[stream_id] = stream
            await self._notify_observers("stream_created", stream)
            return stream

    async def publish(
        self,
        stream_id: str,
        data: Any,
        partition_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[StreamMessage]:
        async with self._lock:
            if stream_id not in self._streams:
                return None
            
            stream = self._streams[stream_id]
            
            message_id = hashlib.md5(f"{stream_id}_{time.time()}".encode()).hexdigest()
            
            sequence_number = len(self._buffer[stream_id]) + 1
            
            message = StreamMessage(
                id=message_id,
                stream_id=stream_id,
                data=data,
                timestamp=time.time(),
                sequence_number=sequence_number,
                partition_key=partition_key,
                metadata=metadata or {}
            )
            
            self._messages[message_id] = message
            
            self._buffer[stream_id].append(message)
            
            await self._process_message(message, stream)
            
            await self._notify_observers("message_published", message)
            
            return message

    async def _process_message(self, message: StreamMessage, stream: StreamConfig) -> None:
        # Apply filters
        for filter_func in self._filter_functions.get(stream.id, []):
            if not await filter_func(message):
                return
        
        # Apply transformations
        for transform_func in self._transform_functions.get(stream.id, []):
            message.data = await transform_func(message.data)
        
        # Process
        for processor in self._processors.get(stream.id, []):
            try:
                if asyncio.iscoroutinefunction(processor):
                    await processor(message)
                else:
                    processor(message)
            except Exception as e:
                logger.error(f"Processor error: {e}")
        
        # Notify subscribers
        for subscriber in self._subscribers.get(stream.id, []):
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(message)
                else:
                    subscriber(message)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")

    async def subscribe(
        self,
        stream_id: str,
        callback: Callable,
        filter_func: Optional[Callable] = None,
        transform_func: Optional[Callable] = None
    ) -> bool:
        async with self._lock:
            if stream_id not in self._streams:
                return False
            
            if callback:
                self._subscribers[stream_id].append(callback)
            
            if filter_func:
                self._filter_functions[stream_id].append(filter_func)
            
            if transform_func:
                self._transform_functions[stream_id].append(transform_func)
            
            return True

    async def unsubscribe(self, stream_id: str, callback: Callable) -> bool:
        async with self._lock:
            if stream_id not in self._subscribers:
                return False
            
            if callback in self._subscribers[stream_id]:
                self._subscribers[stream_id].remove(callback)
                return True
            
            return False

    async def batch_process(
        self,
        stream_id: str,
        batch_size: Optional[int] = None
    ) -> Optional[StreamBatch]:
        async with self._lock:
            if stream_id not in self._streams:
                return None
            
            stream = self._streams[stream_id]
            batch_size = batch_size or stream.batch_size
            
            messages = []
            for _ in range(min(batch_size, len(self._buffer[stream_id]))):
                if self._buffer[stream_id]:
                    messages.append(self._buffer[stream_id].popleft())
            
            if not messages:
                return None
            
            batch = StreamBatch(
                id=hashlib.md5(f"{stream_id}_{time.time()}".encode()).hexdigest(),
                stream_id=stream_id,
                messages=messages,
                size=len(messages),
                timestamp=time.time()
            )
            
            self._batches[batch.id] = batch
            
            await self._process_batch(batch, stream)
            
            await self._notify_observers("batch_processed", batch)
            return batch

    async def _process_batch(self, batch: StreamBatch, stream: StreamConfig) -> None:
        for message in batch.messages:
            await self._process_message(message, stream)

    async def flush_stream(self, stream_id: str) -> int:
        async with self._lock:
            if stream_id not in self._buffer:
                return 0
            
            count = len(self._buffer[stream_id])
            self._buffer[stream_id].clear()
            return count

    async def get_message(self, message_id: str) -> Optional[StreamMessage]:
        return self._messages.get(message_id)

    async def get_messages(
        self,
        stream_id: str,
        limit: int = 100,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[StreamMessage]:
        messages = [m for m in self._messages.values() if m.stream_id == stream_id]
        
        if start_time:
            messages = [m for m in messages if m.timestamp >= start_time]
        if end_time:
            messages = [m for m in messages if m.timestamp <= end_time]
        
        messages.sort(key=lambda m: m.timestamp)
        return messages[-limit:]

    async def get_batch(self, batch_id: str) -> Optional[StreamBatch]:
        return self._batches.get(batch_id)

    async def get_batches(
        self,
        stream_id: str,
        limit: int = 100
    ) -> List[StreamBatch]:
        batches = [b for b in self._batches.values() if b.stream_id == stream_id]
        batches.sort(key=lambda b: b.timestamp, reverse=True)
        return batches[:limit]

    async def compute_metrics(self, stream_id: str) -> Optional[StreamMetrics]:
        if stream_id not in self._streams:
            return None
        
        messages = [m for m in self._messages.values() if m.stream_id == stream_id]
        
        if not messages:
            return StreamMetrics(
                stream_id=stream_id,
                messages_published=0,
                messages_subscribed=0,
                messages_processed=0,
                messages_failed=0,
                bytes_published=0,
                bytes_subscribed=0,
                throughput=0,
                latency_avg=0,
                latency_max=0
            )
        
        messages_published = len(messages)
        messages_processed = len([m for m in messages if m.metadata.get("processed", False)])
        messages_failed = len([m for m in messages if m.metadata.get("failed", False)])
        
        total_bytes = sum(len(str(m.data).encode()) for m in messages)
        
        latencies = [m.metadata.get("latency", 0) for m in messages if m.metadata.get("latency")]
        
        metrics = StreamMetrics(
            stream_id=stream_id,
            messages_published=messages_published,
            messages_subscribed=messages_processed,
            messages_processed=messages_processed,
            messages_failed=messages_failed,
            bytes_published=total_bytes,
            bytes_subscribed=total_bytes,
            throughput=messages_published / max(1, time.time() - min(m.timestamp for m in messages)),
            latency_avg=sum(latencies) / len(latencies) if latencies else 0,
            latency_max=max(latencies) if latencies else 0
        )
        
        self._metrics[stream_id] = metrics
        return metrics

    async def get_metrics(self, stream_id: str) -> Optional[StreamMetrics]:
        if stream_id in self._metrics:
            return self._metrics[stream_id]
        return await self.compute_metrics(stream_id)

    async def get_stream(self, stream_id: str) -> Optional[StreamConfig]:
        return self._streams.get(stream_id)

    async def get_streams(self) -> List[StreamConfig]:
        return list(self._streams.values())

    async def delete_stream(self, stream_id: str) -> bool:
        async with self._lock:
            if stream_id in self._streams:
                self._buffer.pop(stream_id, None)
                self._subscribers.pop(stream_id, None)
                self._processors.pop(stream_id, None)
                self._filter_functions.pop(stream_id, None)
                self._transform_functions.pop(stream_id, None)
                del self._streams[stream_id]
                
                if stream_id in self._batch_tasks:
                    self._batch_tasks[stream_id].cancel()
                    del self._batch_tasks[stream_id]
                
                if stream_id in self._flush_tasks:
                    self._flush_tasks[stream_id].cancel()
                    del self._flush_tasks[stream_id]
                
                return True
            return False

    async def start_batch_processor(
        self,
        stream_id: str,
        interval: float = 5.0
    ) -> None:
        if stream_id not in self._streams:
            return
        
        if stream_id in self._batch_tasks:
            return
        
        async def batch_loop():
            while self._running:
                try:
                    await asyncio.sleep(interval)
                    await self.batch_process(stream_id)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Batch loop error: {e}")
        
        self._batch_tasks[stream_id] = asyncio.create_task(batch_loop())

    async def start_flush_processor(
        self,
        stream_id: str,
        interval: float = 60.0
    ) -> None:
        if stream_id not in self._streams:
            return
        
        if stream_id in self._flush_tasks:
            return
        
        async def flush_loop():
            while self._running:
                try:
                    await asyncio.sleep(interval)
                    count = await self.flush_stream(stream_id)
                    if count > 0:
                        logger.debug(f"Flushed {count} messages from {stream_id}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Flush loop error: {e}")
        
        self._flush_tasks[stream_id] = asyncio.create_task(flush_loop())

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        total_messages = len(self._messages)
        total_batches = len(self._batches)
        total_buffer = sum(len(b) for b in self._buffer.values())
        
        return {
            "streams": len(self._streams),
            "messages": total_messages,
            "batches": total_batches,
            "buffer_size": total_buffer,
            "publishers": len(self._publishers),
            "subscribers": sum(len(s) for s in self._subscribers.values()),
            "processors": sum(len(p) for p in self._processors.values()),
            "running": self._running
        }


__all__ = [
    "StreamType",
    "StreamMode",
    "StreamStatus",
    "StreamConfig",
    "StreamMessage",
    "StreamBatch",
    "StreamMetrics",
    "DataStreamManager"
]
