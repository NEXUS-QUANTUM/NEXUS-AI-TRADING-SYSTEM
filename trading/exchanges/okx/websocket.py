# trading/exchanges/okx/websocket.py
# Nexus AI Trading System - OKX Exchange WebSocket Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - WebSocket Module

This module provides comprehensive WebSocket functionality for the OKX
cryptocurrency exchange, including:

- Real-time market data streaming (ticker, OHLC, trades, order book, spread)
- Private data streaming (positions, orders, balances)
- Subscription management with automatic reconnection
- Heartbeat and ping/pong handling
- Message queuing and processing
- Data aggregation and normalization
- Performance optimization with batching
- Connection pooling and load balancing
- Automatic reconnection with exponential backoff
- Comprehensive error handling
- Message validation and filtering
- Broadcast to multiple handlers
- Metrics and monitoring
- Circuit breaker pattern for resilience
- Graceful shutdown and cleanup

Architecture:
    OKXWebSocket -> Connection Manager -> Subscription Manager
                  -> Message Processor -> Data Distributor
                  -> Reconnection Handler -> Health Monitor

Protocol: WebSocket (wss://ws.okx.com:8443/ws/v5)
Specification: https://www.okx.com/docs-v5/en/#websocket-api
"""

import asyncio
import json
import time
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set, Deque
from collections import deque
import websockets
import aiohttp
from pydantic import BaseModel, Field, validator
import asyncpg
from redis.asyncio import Redis

# Nexus imports
from trading.exchanges.okx.base import OKXBase, OKXConfig, OKXApiType
from trading.exchanges.okx.exceptions import (
    OKXError,
    OKXWebSocketError,
    OKXWebSocketConnectionError,
    OKXWebSocketSubscriptionError,
    OKXRateLimitError,
    OKXAuthenticationError
)
from trading.exchanges.okx.converter import OKXConverter, get_converter
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class OKXWSChannel(str, Enum):
    """OKX WebSocket channels."""
    TICKER = "ticker"
    OHLC = "candle"
    TRADE = "trades"
    SPREAD = "spread"
    BOOK = "books"
    BOOK5 = "books5"
    DEPTH = "depth"
    POSITIONS = "positions"
    BALANCE = "balance"
    ORDERS = "orders"
    ORDER_ALGO = "orders-algo"
    ACCOUNT = "account"


class OKXWSEvent(str, Enum):
    """OKX WebSocket events."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    PONG = "pong"
    LOGIN = "login"
    LOGOUT = "logout"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    SYSTEM = "system"


class OKXWSConnectionStatus(str, Enum):
    """WebSocket connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


class OKXWSMessageType(str, Enum):
    """WebSocket message types."""
    HEARTBEAT = "heartbeat"
    SYSTEM = "system"
    SUBSCRIPTION = "subscription"
    TICKER = "ticker"
    OHLC = "candle"
    TRADE = "trade"
    SPREAD = "spread"
    BOOK_SNAPSHOT = "book_snapshot"
    BOOK_UPDATE = "book_update"
    POSITION = "position"
    ORDER = "order"
    BALANCE = "balance"
    PONG = "pong"
    LOGIN = "login"
    ERROR = "error"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class WSSubscription(BaseModel):
    """WebSocket subscription."""
    channel: OKXWSChannel
    instruments: List[str]
    depth: Optional[int] = None
    interval: Optional[str] = None
    token: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('instruments')
    def validate_instruments(cls, v):
        if not v:
            raise ValueError("At least one instrument is required")
        return v


class WSMessage(BaseModel):
    """WebSocket message."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: OKXWSMessageType
    channel: Optional[OKXWSChannel] = None
    instrument: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    raw: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_private: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WSConnectionState(BaseModel):
    """WebSocket connection state."""
    status: OKXWSConnectionStatus = OKXWSConnectionStatus.DISCONNECTED
    connected_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    reconnect_attempts: int = 0
    reconnect_delay: float = 1.0
    error_count: int = 0
    messages_received: int = 0
    messages_sent: int = 0
    subscriptions: List[WSSubscription] = Field(default_factory=list)


class WSStatistics(BaseModel):
    """WebSocket statistics."""
    total_messages: int = 0
    total_heartbeats: int = 0
    total_errors: int = 0
    total_reconnects: int = 0
    last_error: Optional[str] = None
    messages_per_second: float = 0.0
    latency_ms: float = 0.0
    connection_duration: float = 0.0
    uptime: float = 0.0
    active_subscriptions: int = 0


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- WebSocket messages archive
CREATE TABLE IF NOT EXISTS okx_ws_messages (
    id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    channel VARCHAR(50),
    instrument VARCHAR(50),
    data JSONB NOT NULL,
    raw JSONB,
    is_private BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_okx_ws_messages_type (type),
    INDEX idx_okx_ws_messages_channel (channel),
    INDEX idx_okx_ws_messages_instrument (instrument),
    INDEX idx_okx_ws_messages_timestamp (timestamp)
);

-- WebSocket connection history
CREATE TABLE IF NOT EXISTS okx_ws_connections (
    id SERIAL PRIMARY KEY,
    connection_id VARCHAR(64) NOT NULL,
    status VARCHAR(30) NOT NULL,
    connected_at TIMESTAMP,
    disconnected_at TIMESTAMP,
    duration INTEGER,
    error TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- WebSocket subscription history
CREATE TABLE IF NOT EXISTS okx_ws_subscriptions (
    id SERIAL PRIMARY KEY,
    connection_id VARCHAR(64) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    instruments JSONB NOT NULL,
    subscribed_at TIMESTAMP NOT NULL,
    unsubscribed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);
"""


# =============================================================================
# MAIN WEBSOCKET CLASS
# =============================================================================

class OKXWebSocket:
    """
    Advanced WebSocket manager for OKX exchange.
    
    Features:
    - Real-time data streaming with low latency
    - Automatic reconnection with exponential backoff
    - Subscription management with state recovery
    - Message queuing and batching
    - Data normalization and validation
    - Multiple channel support
    - Private data streaming (authenticated)
    - Heartbeat and ping/pong handling
    - Connection pooling
    - Comprehensive error handling
    - Metrics and monitoring
    - Database persistence
    - Redis caching
    - Circuit breaker pattern
    - Graceful shutdown
    """
    
    def __init__(
        self,
        base: OKXBase,
        config: OKXConfig,
        converter: Optional[OKXConverter] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.base = base
        self.config = config
        self.converter = converter or get_converter()
        self.redis = redis
        self.pool = pool
        
        # WebSocket connection
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connection_id = str(uuid.uuid4())
        
        # Connection state
        self._state = WSConnectionState()
        self._status = OKXWSConnectionStatus.DISCONNECTED
        self._stats = WSStatistics()
        
        # Subscription management
        self._subscriptions: Dict[str, WSSubscription] = {}
        self._subscription_handlers: Dict[str, List[Callable]] = {}
        
        # Message queues
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._processing_tasks: List[asyncio.Task] = []
        
        # Heartbeat
        self._heartbeat_interval = 30
        self._last_heartbeat = 0
        self._ping_task: Optional[asyncio.Task] = None
        
        # Reconnection
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        
        # Circuit breaker
        self._cb = CircuitBreaker(
            name="okx_ws",
            failure_threshold=5,
            recovery_timeout=30
        )
        
        # Rate limit
        self._rate_limiter = {
            'messages': 0,
            'window_start': time.time(),
            'max_per_second': 100  # OKX's rate limit
        }
        
        # Compression
        self._use_compression = True
        
        # Database
        self._db_initialized = False
        
        # Running state
        self._running = False
        self._shutdown_requested = False
        
        # Message buffer for aggregation
        self._buffer: Dict[str, List[WSMessage]] = {}
        self._buffer_size = 100
        self._buffer_ttl = 1.0  # seconds
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        # Authentication state
        self._authenticated = False
        
        logger.info(f"OKXWebSocket initialized with connection ID: {self._connection_id}")
    
    async def initialize(self):
        """Initialize WebSocket module."""
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        self._running = True
        
        # Start message processor
        processor = asyncio.create_task(self._message_processor_loop())
        self._processing_tasks.append(processor)
        
        # Start buffer flusher
        flusher = asyncio.create_task(self._buffer_flusher_loop())
        self._processing_tasks.append(flusher)
        
        logger.info("OKXWebSocket initialized")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def connect(self, authenticate: bool = False):
        """
        Connect to OKX WebSocket.
        
        Args:
            authenticate: Whether to authenticate for private data
        """
        if self._ws and self._status == OKXWSConnectionStatus.CONNECTED:
            return
        
        if self._cb.is_open():
            raise OKXRateLimitError("WebSocket circuit breaker is open")
        
        try:
            self._status = OKXWSConnectionStatus.CONNECTING
            self._state.status = OKXWSConnectionStatus.CONNECTING
            
            ws_url = self._build_ws_url()
            
            logger.info(f"Connecting to WebSocket: {ws_url}")
            
            # Connect with SSL
            self._ws = await websockets.connect(
                ws_url,
                ping_interval=self._heartbeat_interval,
                ping_timeout=10,
                close_timeout=10,
                compression="deflate" if self._use_compression else None,
                ssl=self.config.verify_ssl,
                max_queue=1024
            )
            
            self._status = OKXWSConnectionStatus.CONNECTED
            self._state.status = OKXWSConnectionStatus.CONNECTED
            self._state.connected_at = datetime.utcnow()
            self._state.last_message_at = datetime.utcnow()
            self._state.reconnect_attempts = 0
            self._state.reconnect_delay = 1.0
            self._state.error_count = 0
            
            # Update stats
            self._stats.total_reconnects += 1
            
            # Record connection
            await self._record_connection()
            
            # Start heartbeat
            self._ping_task = asyncio.create_task(self._heartbeat_loop())
            
            # Start message receiver
            receiver = asyncio.create_task(self._message_receiver_loop())
            self._processing_tasks.append(receiver)
            
            # Authenticate if requested
            if authenticate:
                await self._authenticate()
            
            # Resubscribe
            await self._resubscribe()
            
            self._cb.record_success()
            
            logger.info(f"WebSocket connected successfully (ID: {self._connection_id})")
            
        except Exception as e:
            self._status = OKXWSConnectionStatus.ERROR
            self._state.status = OKXWSConnectionStatus.ERROR
            self._state.error_count += 1
            self._stats.total_errors += 1
            self._stats.last_error = str(e)
            
            self._cb.record_failure()
            
            logger.error(f"WebSocket connection error: {e}")
            
            await self._schedule_reconnection()
            
            raise OKXWebSocketConnectionError(f"Connection failed: {e}")
    
    async def disconnect(self):
        """Disconnect from WebSocket."""
        self._shutdown_requested = True
        self._status = OKXWSConnectionStatus.CLOSING
        self._state.status = OKXWSConnectionStatus.CLOSING
        
        if self._ping_task:
            self._ping_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            self._ws = None
        
        self._status = OKXWSConnectionStatus.CLOSED
        self._state.status = OKXWSConnectionStatus.CLOSED
        
        logger.info("WebSocket disconnected")
    
    async def _authenticate(self):
        """Authenticate for private data."""
        try:
            self._status = OKXWSConnectionStatus.AUTHENTICATING
            
            # Get authentication parameters
            timestamp = self.base._get_timestamp()
            message = timestamp + "GET" + "/users/self/verify"
            
            import hmac
            import base64
            import hashlib
            
            signature = hmac.new(
                self.config.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
            signature_b64 = base64.b64encode(signature).decode('utf-8')
            
            auth_msg = {
                "op": "login",
                "args": [{
                    "apiKey": self.config.api_key,
                    "passphrase": self.config.api_passphrase,
                    "timestamp": timestamp,
                    "sign": signature_b64
                }]
            }
            
            await self._ws.send(json.dumps(auth_msg))
            
            # Wait for login response
            response = await self._ws.recv()
            data = json.loads(response)
            
            if data.get('event') == 'login' and data.get('code') == '0':
                self._authenticated = True
                self._status = OKXWSConnectionStatus.AUTHENTICATED
                logger.info("WebSocket authenticated for private data")
            else:
                error_msg = data.get('msg', 'Unknown error')
                raise OKXAuthenticationError(f"Authentication failed: {error_msg}")
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise OKXWebSocketConnectionError(f"Authentication failed: {e}")
    
    async def _resubscribe(self):
        """Resubscribe to all active subscriptions."""
        for sub_key, subscription in self._subscriptions.items():
            try:
                await self.subscribe(subscription)
                logger.info(f"Resubscribed to {sub_key}")
            except Exception as e:
                logger.error(f"Error resubscribing to {sub_key}: {e}")
    
    def _build_ws_url(self) -> str:
        """Build WebSocket URL."""
        base_url = self.config.get_ws_url()
        if self._use_compression:
            base_url += "?compress=true"
        return base_url
    
    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================
    
    async def subscribe(
        self,
        subscription: WSSubscription,
        handler: Optional[Callable] = None
    ):
        """
        Subscribe to a WebSocket channel.
        
        Args:
            subscription: Subscription configuration
            handler: Message handler callback
        """
        if not self._ws or self._status not in [OKXWSConnectionStatus.CONNECTED, OKXWSConnectionStatus.AUTHENTICATED]:
            raise OKXWebSocketError("WebSocket not connected")
        
        try:
            # Build subscription message
            args = {
                "channel": subscription.channel.value,
                "instId": subscription.instruments[0] if len(subscription.instruments) == 1 else ",".join(subscription.instruments)
            }
            
            if subscription.depth:
                args["depth"] = str(subscription.depth)
            if subscription.interval:
                args["interval"] = subscription.interval
            if subscription.token:
                args["token"] = subscription.token
            
            msg = {
                "op": "subscribe",
                "args": [args]
            }
            
            # Send subscription
            await self._ws.send(json.dumps(msg))
            
            # Store subscription
            sub_key = f"{subscription.channel.value}:{','.join(subscription.instruments)}"
            self._subscriptions[sub_key] = subscription
            
            # Register handler
            if handler:
                if sub_key not in self._subscription_handlers:
                    self._subscription_handlers[sub_key] = []
                self._subscription_handlers[sub_key].append(handler)
            
            # Update state
            if subscription not in self._state.subscriptions:
                self._state.subscriptions.append(subscription)
            
            # Record subscription
            await self._record_subscription(subscription)
            
            logger.info(f"Subscribed to {subscription.channel} for {subscription.instruments}")
            
        except Exception as e:
            logger.error(f"Subscription error: {e}")
            raise OKXWebSocketSubscriptionError(
                f"Failed to subscribe to {subscription.channel}: {e}"
            )
    
    async def unsubscribe(self, subscription: WSSubscription):
        """
        Unsubscribe from a WebSocket channel.
        
        Args:
            subscription: Subscription configuration
        """
        if not self._ws or self._status not in [OKXWSConnectionStatus.CONNECTED, OKXWSConnectionStatus.AUTHENTICATED]:
            return
        
        try:
            args = {
                "channel": subscription.channel.value,
                "instId": subscription.instruments[0] if len(subscription.instruments) == 1 else ",".join(subscription.instruments)
            }
            
            msg = {
                "op": "unsubscribe",
                "args": [args]
            }
            
            await self._ws.send(json.dumps(msg))
            
            sub_key = f"{subscription.channel.value}:{','.join(subscription.instruments)}"
            if sub_key in self._subscriptions:
                del self._subscriptions[sub_key]
            
            if sub_key in self._subscription_handlers:
                del self._subscription_handlers[sub_key]
            
            self._state.subscriptions = [
                s for s in self._state.subscriptions if s != subscription
            ]
            
            logger.info(f"Unsubscribed from {subscription.channel} for {subscription.instruments}")
            
        except Exception as e:
            logger.error(f"Unsubscription error: {e}")
            raise OKXWebSocketSubscriptionError(
                f"Failed to unsubscribe from {subscription.channel}: {e}"
            )
    
    def add_handler(
        self,
        channel: OKXWSChannel,
        instruments: List[str],
        handler: Callable
    ):
        """Add a message handler for a subscription."""
        sub_key = f"{channel.value}:{','.join(instruments)}"
        if sub_key not in self._subscription_handlers:
            self._subscription_handlers[sub_key] = []
        self._subscription_handlers[sub_key].append(handler)
    
    def remove_handler(
        self,
        channel: OKXWSChannel,
        instruments: List[str],
        handler: Optional[Callable] = None
    ):
        """Remove a message handler."""
        sub_key = f"{channel.value}:{','.join(instruments)}"
        if sub_key in self._subscription_handlers:
            if handler:
                self._subscription_handlers[sub_key] = [
                    h for h in self._subscription_handlers[sub_key] if h != handler
                ]
            else:
                del self._subscription_handlers[sub_key]
    
    # =========================================================================
    # MESSAGE RECEIVING AND PROCESSING
    # =========================================================================
    
    async def _message_receiver_loop(self):
        """Background loop for receiving WebSocket messages."""
        while self._running and not self._shutdown_requested:
            try:
                if not self._ws:
                    await asyncio.sleep(0.1)
                    continue
                
                message = await self._ws.recv()
                
                if isinstance(message, bytes):
                    try:
                        message = zlib.decompress(message).decode('utf-8')
                    except zlib.error:
                        message = message.decode('utf-8')
                
                data = json.loads(message)
                
                self._stats.total_messages += 1
                self._state.messages_received += 1
                self._state.last_message_at = datetime.utcnow()
                
                ws_message = await self._process_raw_message(data)
                
                await self._message_queue.put(ws_message)
                
            except websockets.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                await self._handle_disconnection()
                break
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
            except Exception as e:
                logger.error(f"Message receiver error: {e}")
                await asyncio.sleep(0.1)
    
    async def _message_processor_loop(self):
        """Background loop for processing messages."""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                
                await self._process_message(message)
                
                self._message_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Message processor error: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_raw_message(self, data: Dict[str, Any]) -> WSMessage:
        """Process raw WebSocket message."""
        # Check for event
        if 'event' in data:
            event = data.get('event')
            
            if event == 'error':
                return WSMessage(
                    type=OKXWSMessageType.ERROR,
                    data=data,
                    raw=data,
                    metadata={"error": data.get('msg', 'Unknown error')}
                )
            elif event == 'login':
                return WSMessage(
                    type=OKXWSMessageType.LOGIN,
                    data=data,
                    raw=data
                )
            elif event == 'subscribe':
                return WSMessage(
                    type=OKXWSMessageType.SUBSCRIPTION,
                    data=data,
                    raw=data
                )
            elif event == 'unsubscribe':
                return WSMessage(
                    type=OKXWSMessageType.SUBSCRIPTION,
                    data=data,
                    raw=data
                )
            elif event == 'pong':
                return WSMessage(
                    type=OKXWSMessageType.PONG,
                    data=data,
                    raw=data
                )
            elif event == 'system':
                return WSMessage(
                    type=OKXWSMessageType.SYSTEM,
                    data=data,
                    raw=data
                )
        
        # Check for data
        if 'arg' in data and 'data' in data:
            channel = data['arg'].get('channel')
            instrument = data['arg'].get('instId')
            
            if channel == 'ticker':
                return WSMessage(
                    type=OKXWSMessageType.TICKER,
                    channel=OKXWSChannel.TICKER,
                    instrument=instrument,
                    data=data['data'][0] if data['data'] else {},
                    raw=data,
                    is_private=False
                )
            elif channel == 'candle':
                return WSMessage(
                    type=OKXWSMessageType.OHLC,
                    channel=OKXWSChannel.OHLC,
                    instrument=instrument,
                    data=data['data'],
                    raw=data,
                    is_private=False
                )
            elif channel == 'trades':
                return WSMessage(
                    type=OKXWSMessageType.TRADE,
                    channel=OKXWSChannel.TRADE,
                    instrument=instrument,
                    data=data['data'],
                    raw=data,
                    is_private=False
                )
            elif channel in ['books', 'books5']:
                return WSMessage(
                    type=OKXWSMessageType.BOOK_SNAPSHOT if data['data'][0].get('action') == 'snapshot' else OKXWSMessageType.BOOK_UPDATE,
                    channel=OKXWSChannel.BOOK,
                    instrument=instrument,
                    data=data['data'],
                    raw=data,
                    is_private=False
                )
            elif channel == 'positions':
                return WSMessage(
                    type=OKXWSMessageType.POSITION,
                    channel=OKXWSChannel.POSITIONS,
                    instrument=instrument,
                    data=data['data'],
                    raw=data,
                    is_private=True
                )
            elif channel == 'orders':
                return WSMessage(
                    type=OKXWSMessageType.ORDER,
                    channel=OKXWSChannel.ORDERS,
                    instrument=instrument,
                    data=data['data'],
                    raw=data,
                    is_private=True
                )
            elif channel == 'balance':
                return WSMessage(
                    type=OKXWSMessageType.BALANCE,
                    channel=OKXWSChannel.BALANCE,
                    instrument=instrument,
                    data=data['data'],
                    raw=data,
                    is_private=True
                )
        
        return WSMessage(
            type=OKXWSMessageType.ERROR,
            data=data,
            raw=data,
            metadata={"error": "Unknown message format"}
        )
    
    async def _process_message(self, message: WSMessage):
        """Process a single message."""
        try:
            if message.type == OKXWSMessageType.PONG:
                self._stats.total_heartbeats += 1
                self._state.last_heartbeat_at = datetime.utcnow()
                return
            
            if self.pool:
                await self._save_message(message)
            
            if self.redis:
                await self._cache_message(message)
            
            await self._dispatch_message(message)
            
            await self._update_statistics(message)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _dispatch_message(self, message: WSMessage):
        """Dispatch message to handlers."""
        if not message.channel:
            return
        
        sub_key = f"{message.channel.value}:{message.instrument}"
        
        if sub_key in self._subscription_handlers:
            for handler in self._subscription_handlers[sub_key]:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
        
        channel_key = message.channel.value
        if channel_key in self._subscription_handlers:
            for handler in self._subscription_handlers[channel_key]:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
    
    # =========================================================================
    # HEARTBEAT
    # =========================================================================
    
    async def _heartbeat_loop(self):
        """Heartbeat loop."""
        while self._running and self._status in [OKXWSConnectionStatus.CONNECTED, OKXWSConnectionStatus.AUTHENTICATED]:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                
                if not self._ws:
                    continue
                
                ping_msg = {"op": "ping"}
                await self._ws.send(json.dumps(ping_msg))
                self._state.messages_sent += 1
                self._last_heartbeat = time.time()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(1)
    
    # =========================================================================
    # RECONNECTION
    # =========================================================================
    
    async def _handle_disconnection(self):
        """Handle disconnection."""
        if self._shutdown_requested:
            return
        
        self._status = OKXWSConnectionStatus.DISCONNECTED
        self._state.status = OKXWSConnectionStatus.DISCONNECTED
        
        await self._record_disconnection()
        
        await self._schedule_reconnection()
    
    async def _schedule_reconnection(self):
        """Schedule reconnection with exponential backoff."""
        if self._shutdown_requested:
            return
        
        self._reconnect_attempts += 1
        delay = min(
            self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            self._max_reconnect_delay
        )
        
        logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts})")
        
        self._status = OKXWSConnectionStatus.RECONNECTING
        self._state.status = OKXWSConnectionStatus.RECONNECTING
        
        await asyncio.sleep(delay)
        
        if not self._shutdown_requested:
            try:
                await self.connect(authenticate=False)
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                await self._schedule_reconnection()
    
    # =========================================================================
    # BUFFERING AND AGGREGATION
    # =========================================================================
    
    async def _buffer_flusher_loop(self):
        """Background loop for flushing message buffer."""
        while self._running:
            try:
                await asyncio.sleep(self._buffer_ttl)
                
                async with self._lock:
                    for key, messages in list(self._buffer.items()):
                        if messages:
                            await self._process_buffer(key, messages)
                            self._buffer[key] = []
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Buffer flusher error: {e}")
    
    async def _process_buffer(self, key: str, messages: List[WSMessage]):
        """Process a buffer of messages."""
        if messages and messages[0].type == OKXWSMessageType.TRADE:
            aggregated = self._aggregate_trades(messages)
            await self._dispatch_message(aggregated)
        elif messages and messages[0].type == OKXWSMessageType.BOOK_UPDATE:
            pass
        else:
            for message in messages:
                await self._dispatch_message(message)
    
    def _aggregate_trades(self, messages: List[WSMessage]) -> WSMessage:
        """Aggregate multiple trade messages."""
        trades = []
        for msg in messages:
            if msg.type == OKXWSMessageType.TRADE:
                if isinstance(msg.data, list):
                    trades.extend(msg.data)
                elif isinstance(msg.data, dict) and 'trades' in msg.data:
                    trades.extend(msg.data['trades'])
        
        return WSMessage(
            type=OKXWSMessageType.TRADE,
            channel=OKXWSChannel.TRADE,
            instrument=messages[0].instrument if messages else None,
            data={"trades": trades, "aggregated": True},
            is_private=False,
            metadata={"count": len(trades)}
        )
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_message(self, message: WSMessage):
        """Save message to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_ws_messages (
                        id, type, channel, instrument, data, raw,
                        is_private, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    message.id,
                    message.type.value,
                    message.channel.value if message.channel else None,
                    message.instrument,
                    json.dumps(message.data, default=str),
                    json.dumps(message.raw, default=str) if message.raw else None,
                    message.is_private,
                    message.timestamp
                )
        except Exception as e:
            logger.error(f"Error saving message: {e}")
    
    async def _record_connection(self):
        """Record connection in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_ws_connections (
                        connection_id, status, connected_at, metadata
                    ) VALUES ($1, $2, $3, $4)
                    """,
                    self._connection_id,
                    self._status.value,
                    datetime.utcnow(),
                    json.dumps({"subscriptions": len(self._subscriptions)})
                )
        except Exception as e:
            logger.error(f"Error recording connection: {e}")
    
    async def _record_disconnection(self):
        """Record disconnection in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                duration = None
                if self._state.connected_at:
                    duration = int((datetime.utcnow() - self._state.connected_at).total_seconds())
                
                await conn.execute(
                    """
                    UPDATE okx_ws_connections
                    SET status = $1, disconnected_at = $2, duration = $3
                    WHERE connection_id = $4 AND disconnected_at IS NULL
                    """,
                    self._status.value,
                    datetime.utcnow(),
                    duration,
                    self._connection_id
                )
        except Exception as e:
            logger.error(f"Error recording disconnection: {e}")
    
    async def _record_subscription(self, subscription: WSSubscription):
        """Record subscription in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_ws_subscriptions (
                        connection_id, channel, instruments, subscribed_at, metadata                    ) VALUES ($1, $2, $3, $4, $5)
                    """,
                    self._connection_id,
                    subscription.channel.value,
                    json.dumps(subscription.instruments),
                    datetime.utcnow(),
                    json.dumps(subscription.metadata)
                )
        except Exception as e:
            logger.error(f"Error recording subscription: {e}")
    
    async def _cache_message(self, message: WSMessage):
        """Cache message in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"okx:ws:{message.channel.value}:{message.instrument}"
            await self.redis.setex(
                key,
                60,
                json.dumps(message.data, default=str)
            )
        except Exception as e:
            logger.error(f"Error caching message: {e}")
    
    # =========================================================================
    # STATISTICS AND METRICS
    # =========================================================================
    
    async def _update_statistics(self, message: WSMessage):
        """Update statistics."""
        now = time.time()
        if now - self._rate_limiter['window_start'] > 1:
            self._stats.messages_per_second = self._rate_limiter['messages']
            self._rate_limiter['messages'] = 0
            self._rate_limiter['window_start'] = now
        else:
            self._rate_limiter['messages'] += 1
        
        self._stats.active_subscriptions = len(self._subscriptions)
        
        if self._state.connected_at:
            self._stats.uptime = (datetime.utcnow() - self._state.connected_at).total_seconds()
    
    async def get_statistics(self) -> WSStatistics:
        """Get WebSocket statistics."""
        return self._stats
    
    async def get_connection_state(self) -> WSConnectionState:
        """Get connection state."""
        return self._state
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """
        Send a message via WebSocket.
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully
        """
        if not self._ws or self._status not in [OKXWSConnectionStatus.CONNECTED, OKXWSConnectionStatus.AUTHENTICATED]:
            return False
        
        try:
            await self._ws.send(json.dumps(message))
            self._state.messages_sent += 1
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._status in [OKXWSConnectionStatus.CONNECTED, OKXWSConnectionStatus.AUTHENTICATED]
    
    def is_authenticated(self) -> bool:
        """Check if WebSocket is authenticated."""
        return self._authenticated and self.is_connected()
    
    def get_subscriptions(self) -> List[WSSubscription]:
        """Get all active subscriptions."""
        return list(self._subscriptions.values())
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown WebSocket module."""
        self._shutdown_requested = True
        self._running = False
        
        await self.disconnect()
        
        for task in self._processing_tasks:
            if not task.done():
                task.cancel()
        
        if self._processing_tasks:
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)
        
        logger.info("OKXWebSocket shutdown complete")


# =============================================================================
# WEBSOCKET FACTORY
# =============================================================================

class OKXWebSocketFactory:
    """Factory for creating WebSocket connections."""
    
    _instances: Dict[str, OKXWebSocket] = {}
    
    @classmethod
    def get_or_create(
        cls,
        base: OKXBase,
        config: OKXConfig,
        converter: Optional[OKXConverter] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ) -> OKXWebSocket:
        """Get or create a WebSocket instance."""
        key = f"{config.api_key[:8]}_{config.environment}"
        
        if key not in cls._instances:
            ws = OKXWebSocket(base, config, converter, redis, pool)
            cls._instances[key] = ws
        
        return cls._instances[key]
    
    @classmethod
    async def shutdown_all(cls):
        """Shutdown all WebSocket instances."""
        for instance in cls._instances.values():
            await instance.shutdown()
        cls._instances.clear()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OKXWebSocket',
    'OKXWebSocketFactory',
    'OKXWSChannel',
    'OKXWSEvent',
    'OKXWSConnectionStatus',
    'OKXWSMessageType',
    'WSSubscription',
    'WSMessage',
    'WSConnectionState',
    'WSStatistics'
]
