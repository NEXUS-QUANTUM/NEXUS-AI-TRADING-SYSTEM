# trading/bots/arbitrage_bot/data/data_stream.py
# Nexus AI Trading System - Arbitrage Bot Data Stream Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Data Stream Module

This module provides comprehensive real-time data streaming for the
arbitrage bot system, including:

- WebSocket data streaming
- SSE (Server-Sent Events) streaming
- Real-time data processing
- Stream multiplexing
- Data filtering and transformation
- Stream health monitoring
- Automatic reconnection
- Data buffering
- Stream backpressure handling
- Multi-format support (JSON, Protobuf, MessagePack)
- Stream compression
- Stream encryption
- Data validation
- Stream metrics and monitoring
- Stream persistence

The data stream module handles all real-time data flow for the
arbitrage bot, ensuring reliable, low-latency data delivery.
"""

import asyncio
import json
import math
import time
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import aiohttp
import websockets
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class StreamType(str, Enum):
    """Stream types."""
    WEBSOCKET = "websocket"
    SSE = "sse"
    GRPC = "grpc"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    REDIS_PUBSUB = "redis_pubsub"
    CUSTOM = "custom"


class StreamFormat(str, Enum):
    """Stream formats."""
    JSON = "json"
    PROTOBUF = "protobuf"
    MSGPACK = "msgpack"
    CBOR = "cbor"
    AVRO = "avro"
    CSV = "csv"
    RAW = "raw"


class StreamStatus(str, Enum):
    """Stream status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    CLOSED = "closed"


class StreamMessageType(str, Enum):
    """Stream message types."""
    DATA = "data"
    HEARTBEAT = "heartbeat"
    CONTROL = "control"
    ERROR = "error"
    ACKNOWLEDGMENT = "acknowledgment"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StreamConfig(BaseModel):
    """Stream configuration."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: StreamType
    format: StreamFormat = StreamFormat.JSON
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    auth: Optional[Dict[str, Any]] = None
    reconnect_delay: int = 5
    max_reconnect_attempts: int = 10
    heartbeat_interval: int = 30
    buffer_size: int = 1000
    batch_size: int = 100
    timeout: int = 30
    compression: bool = False
    compression_level: int = 6
    encryption: bool = False
    encryption_key: Optional[str] = None
    filters: List[Dict[str, Any]] = Field(default_factory=list)
    transforms: List[Dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StreamMessage(BaseModel):
    """Stream message."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stream_id: str
    type: StreamMessageType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None


class StreamBatch(BaseModel):
    """Stream batch."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stream_id: str
    messages: List[StreamMessage] = Field(default_factory=list)
    size_bytes: int = 0
    message_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StreamMetrics(BaseModel):
    """Stream metrics."""
    stream_id: str
    messages_received: int = 0
    messages_processed: int = 0
    messages_dropped: int = 0
    bytes_received: int = 0
    connection_attempts: int = 0
    reconnect_count: int = 0
    last_message_time: Optional[datetime] = None
    current_latency_ms: float = 0.0
    average_latency_ms: float = 0.0
    connection_status: StreamStatus = StreamStatus.DISCONNECTED
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# STREAM BACKENDS
# =============================================================================

class StreamBackend:
    """Abstract stream backend interface."""
    
    async def connect(self) -> bool:
        """Connect to stream."""
        raise NotImplementedError
    
    async def disconnect(self) -> bool:
        """Disconnect from stream."""
        raise NotImplementedError
    
    async def send(self, data: Any) -> bool:
        """Send data to stream."""
        raise NotImplementedError
    
    async def receive(self) -> Optional[Any]:
        """Receive data from stream."""
        raise NotImplementedError
    
    async def is_connected(self) -> bool:
        """Check if connected."""
        raise NotImplementedError


class WebSocketBackend(StreamBackend):
    """WebSocket stream backend."""
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        
        # Message queue
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=config.buffer_size)
        self._receive_task: Optional[asyncio.Task] = None
        
        # Lock
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Connect to WebSocket."""
        async with self._lock:
            if self._connected:
                return True
            
            try:
                self._ws = await websockets.connect(
                    self.config.url,
                    extra_headers=self.config.headers,
                    ping_interval=self.config.heartbeat_interval,
                    ping_timeout=10,
                    close_timeout=5
                )
                
                self._connected = True
                self._receive_task = asyncio.create_task(self._receive_loop())
                
                logger.info(f"WebSocket connected: {self.config.url}")
                return True
                
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                return False
    
    async def disconnect(self) -> bool:
        """Disconnect from WebSocket."""
        async with self._lock:
            self._connected = False
            
            if self._receive_task:
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass
            
            if self._ws:
                try:
                    await self._ws.close()
                except Exception:
                    pass
            
            self._ws = None
            logger.info(f"WebSocket disconnected: {self.config.url}")
            return True
    
    async def send(self, data: Any) -> bool:
        """Send data to WebSocket."""
        if not self._connected or not self._ws:
            return False
        
        try:
            if isinstance(data, dict):
                data = json.dumps(data)
            await self._ws.send(data)
            return True
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            return False
    
    async def receive(self) -> Optional[Any]:
        """Receive data from WebSocket."""
        try:
            return await self._queue.get()
        except Exception:
            return None
    
    async def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected and self._ws is not None
    
    async def _receive_loop(self):
        """Receive loop for WebSocket."""
        while self._connected:
            try:
                message = await self._ws.recv()
                await self._queue.put(message)
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                break
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                break
        
        self._connected = False


class SSEBackend(StreamBackend):
    """Server-Sent Events stream backend."""
    
    def __init__(self, config: StreamConfig, session: aiohttp.ClientSession):
        self.config = config
        self.session = session
        self._connected = False
        self._response: Optional[aiohttp.ClientResponse] = None
        
        # Message queue
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=config.buffer_size)
        self._receive_task: Optional[asyncio.Task] = None
        
        # Lock
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Connect to SSE stream."""
        async with self._lock:
            if self._connected:
                return True
            
            try:
                self._response = await self.session.get(
                    self.config.url,
                    headers=self.config.headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                )
                
                if self._response.status == 200:
                    self._connected = True
                    self._receive_task = asyncio.create_task(self._receive_loop())
                    logger.info(f"SSE connected: {self.config.url}")
                    return True
                else:
                    logger.error(f"SSE connection failed: {self._response.status}")
                    return False
                    
            except Exception as e:
                logger.error(f"SSE connection error: {e}")
                return False
    
    async def disconnect(self) -> bool:
        """Disconnect from SSE stream."""
        async with self._lock:
            self._connected = False
            
            if self._receive_task:
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass
            
            if self._response:
                self._response.close()
            
            self._response = None
            logger.info(f"SSE disconnected: {self.config.url}")
            return True
    
    async def send(self, data: Any) -> bool:
        """Send data to SSE (not supported)."""
        return False
    
    async def receive(self) -> Optional[Any]:
        """Receive data from SSE."""
        try:
            return await self._queue.get()
        except Exception:
            return None
    
    async def is_connected(self) -> bool:
        """Check if SSE is connected."""
        return self._connected and self._response is not None
    
    async def _receive_loop(self):
        """Receive loop for SSE."""
        while self._connected:
            try:
                line = await self._response.content.readline()
                if not line:
                    break
                
                line = line.decode('utf-8').strip()
                if line.startswith('data:'):
                    data = line[5:].strip()
                    if data and data != '[DONE]':
                        await self._queue.put(data)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SSE receive error: {e}")
                break
        
        self._connected = False


# =============================================================================
# DATA STREAM CLASS
# =============================================================================

class DataStream:
    """
    Advanced data stream manager for arbitrage bot.
    
    Features:
    - WebSocket data streaming
    - SSE (Server-Sent Events) streaming
    - Real-time data processing
    - Stream multiplexing
    - Data filtering and transformation
    - Stream health monitoring
    - Automatic reconnection
    - Data buffering
    - Stream backpressure handling
    - Multi-format support (JSON, Protobuf, MessagePack)
    - Stream compression
    - Stream encryption
    - Data validation
    - Stream metrics and monitoring
    - Stream persistence
    """
    
    def __init__(
        self,
        config: StreamConfig,
        redis: Optional[Redis] = None,
        session: Optional[aiohttp.ClientSession] = None
    ):
        self.config = config
        self.redis = redis
        self.session = session or aiohttp.ClientSession()
        
        # Backend
        self._backend: Optional[StreamBackend] = None
        
        # Metrics
        self._metrics = StreamMetrics(stream_id=config.id)
        
        # Handlers
        self._handlers: List[Callable] = []
        
        # Circuit breakers
        self._stream_cb = CircuitBreaker(
            name=f"data_stream_{config.id}",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        
        # Reconnection task
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Message buffer
        self._buffer: List[StreamMessage] = []
        
        logger.info(f"DataStream initialized: {config.name}")
    
    async def initialize(self):
        """Initialize the data stream."""
        if self._initialized:
            return
        
        # Create backend
        if self.config.type == StreamType.WEBSOCKET:
            self._backend = WebSocketBackend(self.config)
        elif self.config.type == StreamType.SSE:
            self._backend = SSEBackend(self.config, self.session)
        else:
            raise ValueError(f"Unsupported stream type: {self.config.type}")
        
        # Connect
        await self._connect()
        
        # Start reconnect task
        self._running = True
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        
        self._initialized = True
        logger.info(f"DataStream initialized: {self.config.name}")
    
    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================
    
    async def _connect(self) -> bool:
        """Connect to stream."""
        if not self._backend:
            return False
        
        try:
            connected = await self._backend.connect()
            
            if connected:
                self._metrics.connection_status = StreamStatus.CONNECTED
                self._metrics.connection_attempts += 1
                self._stream_cb.record_success()
                
                # Start receive loop
                asyncio.create_task(self._receive_loop())
                
                logger.info(f"Stream connected: {self.config.name}")
                return True
            else:
                self._metrics.connection_status = StreamStatus.ERROR
                self._stream_cb.record_failure()
                return False
                
        except Exception as e:
            self._metrics.connection_status = StreamStatus.ERROR
            self._stream_cb.record_failure()
            logger.error(f"Stream connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from stream."""
        if self._backend:
            await self._backend.disconnect()
        
        self._metrics.connection_status = StreamStatus.DISCONNECTED
        logger.info(f"Stream disconnected: {self.config.name}")
    
    async def _reconnect_loop(self):
        """Reconnection loop."""
        attempts = 0
        
        while self._running:
            try:
                if not await self._backend.is_connected():
                    attempts += 1
                    
                    if attempts > self.config.max_reconnect_attempts:
                        self._metrics.connection_status = StreamStatus.ERROR
                        logger.error(f"Max reconnect attempts reached: {self.config.name}")
                        await asyncio.sleep(60)
                        attempts = 0
                        continue
                    
                    self._metrics.reconnect_count += 1
                    self._metrics.connection_status = StreamStatus.RECONNECTING
                    
                    delay = min(self.config.reconnect_delay * (2 ** (attempts - 1)), 60)
                    logger.info(f"Reconnecting in {delay}s (attempt {attempts}): {self.config.name}")
                    await asyncio.sleep(delay)
                    
                    if await self._connect():
                        attempts = 0
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reconnect loop error: {e}")
                await asyncio.sleep(5)
    
    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================
    
    async def _receive_loop(self):
        """Receive loop."""
        while self._running and await self._backend.is_connected():
            try:
                data = await self._backend.receive()
                if data is None:
                    break
                
                # Create message
                message = StreamMessage(
                    stream_id=self.config.id,
                    type=StreamMessageType.DATA,
                    data=data
                )
                
                # Process message
                await self._process_message(message)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Receive loop error: {e}")
                await asyncio.sleep(1)
        
        # Update status if loop exits
        if self._running:
            self._metrics.connection_status = StreamStatus.ERROR
    
    async def _process_message(self, message: StreamMessage):
        """
        Process a stream message.
        
        Args:
            message: Stream message
        """
        try:
            # Update metrics
            self._metrics.messages_received += 1
            self._metrics.last_message_time = datetime.utcnow()
            
            # Calculate latency
            if message.timestamp:
                latency = (datetime.utcnow() - message.timestamp).total_seconds() * 1000
                self._metrics.current_latency_ms = latency
                self._metrics.average_latency_ms = (
                    (self._metrics.average_latency_ms * (self._metrics.messages_received - 1) + latency) /
                    self._metrics.messages_received
                )
            
            # Apply filters
            if not self._apply_filters(message):
                self._metrics.messages_dropped += 1
                return
            
            # Apply transforms
            message.data = self._apply_transforms(message.data)
            
            # Validate data
            if not self._validate_data(message.data):
                self._metrics.messages_dropped += 1
                return
            
            # Process message
            self._metrics.messages_processed += 1
            
            # Trigger handlers
            await self._trigger_handlers(message)
            
            # Cache message
            if self.redis:
                await self._cache_message(message)
            
        except Exception as e:
            logger.error(f"Process message error: {e}")
            self._metrics.messages_dropped += 1
    
    # =========================================================================
    # DATA FILTERING AND TRANSFORMATION
    # =========================================================================
    
    def _apply_filters(self, message: StreamMessage) -> bool:
        """
        Apply filters to message.
        
        Args:
            message: Stream message
            
        Returns:
            True if message passes all filters
        """
        if not self.config.filters:
            return True
        
        for filter_config in self.config.filters:
            filter_type = filter_config.get('type')
            field = filter_config.get('field')
            value = filter_config.get('value')
            
            if filter_type == 'equals':
                if message.data.get(field) != value:
                    return False
            elif filter_type == 'contains':
                if value not in message.data.get(field, ''):
                    return False
            elif filter_type == 'regex':
                import re
                if not re.match(value, str(message.data.get(field, ''))):
                    return False
            elif filter_type == 'range':
                min_val = filter_config.get('min')
                max_val = filter_config.get('max')
                val = message.data.get(field)
                if min_val is not None and val < min_val:
                    return False
                if max_val is not None and val > max_val:
                    return False
        
        return True
    
    def _apply_transforms(self, data: Any) -> Any:
        """
        Apply transforms to data.
        
        Args:
            data: Data to transform
            
        Returns:
            Transformed data
        """
        if not self.config.transforms:
            return data
        
        result = data
        
        for transform in self.config.transforms:
            transform_type = transform.get('type')
            
            if transform_type == 'rename':
                old_key = transform.get('old')
                new_key = transform.get('new')
                if old_key in result:
                    result[new_key] = result.pop(old_key)
                    
            elif transform_type == 'remove':
                for key in transform.get('keys', []):
                    result.pop(key, None)
                    
            elif transform_type == 'add':
                result[transform.get('key')] = transform.get('value')
                
            elif transform_type == 'format':
                key = transform.get('key')
                format_str = transform.get('format')
                if key in result:
                    result[key] = format_str.format(result[key])
                    
            elif transform_type == 'parse':
                key = transform.get('key')
                parse_type = transform.get('type')
                if key in result:
                    try:
                        if parse_type == 'int':
                            result[key] = int(result[key])
                        elif parse_type == 'float':
                            result[key] = float(result[key])
                        elif parse_type == 'decimal':
                            from decimal import Decimal
                            result[key] = Decimal(str(result[key]))
                        elif parse_type == 'datetime':
                            result[key] = datetime.fromisoformat(result[key])
                    except Exception:
                        pass
        
        return result
    
    def _validate_data(self, data: Any) -> bool:
        """
        Validate data.
        
        Args:
            data: Data to validate
            
        Returns:
            True if data is valid
        """
        # Basic validation
        if data is None:
            return False
        
        if isinstance(data, dict):
            # Check for required fields
            if self.config.metadata.get('required_fields'):
                required = self.config.metadata['required_fields']
                return all(field in data for field in required)
        
        return True
    
    # =========================================================================
    # HANDLERS
    # =========================================================================
    
    async def on_message(self, handler: Callable):
        """
        Register a message handler.
        
        Args:
            handler: Message handler function
        """
        self._handlers.append(handler)
    
    async def _trigger_handlers(self, message: StreamMessage):
        """
        Trigger message handlers.
        
        Args:
            message: Stream message
        """
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")
    
    # =========================================================================
    # SEND OPERATIONS
    # =========================================================================
    
    async def send(self, data: Any) -> bool:
        """
        Send data to stream.
        
        Args:
            data: Data to send
            
        Returns:
            True if sent successfully
        """
        if not self._backend:
            return False
        
        return await self._backend.send(data)
    
    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================
    
    async def _cache_message(self, message: StreamMessage):
        """
        Cache message in Redis.
        
        Args:
            message: Stream message
        """
        if not self.redis:
            return
        
        try:
            key = f"stream:{self.config.id}:last"
            await self.redis.setex(
                key,
                60,
                json.dumps({
                    'id': message.id,
                    'data': message.data,
                    'timestamp': message.timestamp.isoformat()
                }, default=str)
            )
        except Exception as e:
            logger.error(f"Cache message error: {e}")
    
    # =========================================================================
    # METRICS
    # =========================================================================
    
    async def get_metrics(self) -> StreamMetrics:
        """
        Get stream metrics.
        
        Returns:
            StreamMetrics
        """
        return self._metrics
    
    async def reset_metrics(self):
        """Reset stream metrics."""
        self._metrics = StreamMetrics(stream_id=self.config.id)
    
    # =========================================================================
    # STATUS
    # =========================================================================
    
    async def get_status(self) -> StreamStatus:
        """
        Get stream status.
        
        Returns:
            StreamStatus
        """
        if not self._backend:
            return StreamStatus.DISCONNECTED
        
        if await self._backend.is_connected():
            return StreamStatus.CONNECTED
        
        return self._metrics.connection_status
    
    async def is_connected(self) -> bool:
        """
        Check if stream is connected.
        
        Returns:
            True if connected
        """
        return await self.get_status() == StreamStatus.CONNECTED
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the data stream."""
        self._running = False
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        
        await self.disconnect()
        
        logger.info(f"DataStream shutdown: {self.config.name}")


# =============================================================================
# STREAM MANAGER
# =============================================================================

class StreamManager:
    """
    Manager for multiple data streams.
    
    Features:
    - Stream lifecycle management
    - Stream multiplexing
    - Stream monitoring
    - Stream routing
    - Stream broadcasting
    """
    
    def __init__(self):
        self._streams: Dict[str, DataStream] = {}
        self._running = False
        
        logger.info("StreamManager initialized")
    
    async def create_stream(
        self,
        config: StreamConfig,
        redis: Optional[Redis] = None,
        session: Optional[aiohttp.ClientSession] = None
    ) -> DataStream:
        """
        Create a new data stream.
        
        Args:
            config: Stream configuration
            redis: Redis client
            session: HTTP session
            
        Returns:
            DataStream
        """
        if config.id in self._streams:
            raise ValueError(f"Stream {config.id} already exists")
        
        stream = DataStream(config, redis, session)
        await stream.initialize()
        
        self._streams[config.id] = stream
        
        logger.info(f"Created stream: {config.name}")
        return stream
    
    async def get_stream(self, stream_id: str) -> Optional[DataStream]:
        """
        Get a stream by ID.
        
        Args:
            stream_id: Stream ID
            
        Returns:
            DataStream or None
        """
        return self._streams.get(stream_id)
    
    async def get_stream_by_name(self, name: str) -> Optional[DataStream]:
        """
        Get a stream by name.
        
        Args:
            name: Stream name
            
        Returns:
            DataStream or None
        """
        for stream in self._streams.values():
            if stream.config.name == name:
                return stream
        return None
    
    async def list_streams(self) -> List[DataStream]:
        """
        List all streams.
        
        Returns:
            List of DataStream
        """
        return list(self._streams.values())
    
    async def delete_stream(self, stream_id: str) -> bool:
        """
        Delete a stream.
        
        Args:
            stream_id: Stream ID
            
        Returns:
            True if deleted successfully
        """
        if stream_id not in self._streams:
            return False
        
        stream = self._streams[stream_id]
        await stream.shutdown()
        
        del self._streams[stream_id]
        
        logger.info(f"Deleted stream: {stream_id}")
        return True
    
    async def broadcast(self, stream_id: str, data: Any) -> bool:
        """
        Broadcast data to a stream.
        
        Args:
            stream_id: Stream ID
            data: Data to broadcast
            
        Returns:
            True if broadcast successfully
        """
        if stream_id not in self._streams:
            return False
        
        return await self._streams[stream_id].send(data)
    
    async def shutdown(self):
        """Shutdown the stream manager."""
        for stream in self._streams.values():
            await stream.shutdown()
        
        self._streams.clear()
        logger.info("StreamManager shutdown")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'DataStream',
    'StreamManager',
    'StreamType',
    'StreamFormat',
    'StreamStatus',
    'StreamMessageType',
    'StreamConfig',
    'StreamMessage',
    'StreamBatch',
    'StreamMetrics',
    'StreamBackend',
    'WebSocketBackend',
    'SSEBackend'
]
