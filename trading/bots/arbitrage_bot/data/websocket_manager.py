"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot WebSocket Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced WebSocket management system with:
- Multi-exchange WebSocket connections
- Real-time price streaming
- Automatic reconnection with backoff
- Message queuing and processing
- Heartbeat monitoring
- Subscription management
- Message validation and normalization
- Performance metrics
"""

import asyncio
import json
import logging
import ssl
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable

import aiohttp
from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType
from pydantic import BaseModel, Field, validator

# Local imports
from .base import BaseWebSocketManager
from .exceptions import (
    WebSocketManagerError,
    WebSocketConnectionError,
    WebSocketSubscriptionError,
    WebSocketMessageError,
    WebSocketTimeoutError,
)
from .config import WebSocketManagerConfig
from .constants import (
    WEBSOCKET_RECONNECT_DELAY,
    WEBSOCKET_MAX_RECONNECT_ATTEMPTS,
    WEBSOCKET_HEARTBEAT_INTERVAL,
    WEBSOCKET_MESSAGE_TIMEOUT,
    WEBSOCKET_QUEUE_SIZE,
)

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class ConnectionState(str, Enum):
    """WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"
    FAILED = "failed"


class MessageType(str, Enum):
    """WebSocket message type."""
    PRICE = "price"
    TICKER = "ticker"
    ORDER_BOOK = "order_book"
    TRADE = "trade"
    CANDLE = "candle"
    HEARTBEAT = "heartbeat"
    SUBSCRIPTION = "subscription"
    UNSUBSCRIPTION = "unsubscription"
    ERROR = "error"
    PONG = "pong"
    PING = "ping"
    UNKNOWN = "unknown"


class ExchangeWebSocketConfig(BaseModel):
    """Exchange WebSocket configuration."""
    
    exchange: str
    url: str
    ping_interval: int = 30
    ping_timeout: int = 10
    reconnect_delay: int = 5
    max_reconnect_attempts: int = 10
    subscriptions: List[Dict[str, Any]] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    ssl: bool = True
    verify_ssl: bool = True
    message_timeout: int = 60
    heartbeat_interval: int = 30


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class WebSocketMessage:
    """WebSocket message container."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    type: MessageType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    received_at: float = field(default_factory=time.time)
    processed: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'exchange': self.exchange,
            'type': self.type.value if isinstance(self.type, MessageType) else self.type,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'received_at': self.received_at,
            'processed': self.processed,
            'error': self.error,
        }


@dataclass
class WebSocketConnection:
    """WebSocket connection information."""
    
    exchange: str
    state: ConnectionState
    socket: Optional[ClientWebSocketResponse] = None
    session: Optional[ClientSession] = None
    reconnect_attempts: int = 0
    last_reconnect_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    messages_received: int = 0
    messages_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    errors: int = 0
    subscriptions: Set[str] = field(default_factory=set)
    ping_task: Optional[asyncio.Task] = None
    receive_task: Optional[asyncio.Task] = None


@dataclass
class WebSocketMetrics:
    """WebSocket performance metrics."""
    
    exchange: str
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    total_reconnections: int = 0
    messages_received: int = 0
    messages_sent: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    last_message_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None


# ============================================================
# WEBSOCKET MANAGER IMPLEMENTATION
# ============================================================

class WebSocketManager(BaseWebSocketManager):
    """
    Advanced WebSocket manager with:
    - Multi-exchange WebSocket connections
    - Automatic reconnection with exponential backoff
    - Real-time message processing
    - Subscription management
    - Heartbeat monitoring
    - Performance metrics
    """

    def __init__(
        self,
        config: Optional[WebSocketManagerConfig] = None,
        redis_client: Optional[Any] = None,
        max_queue_size: int = 10000,
    ):
        """
        Initialize WebSocket manager.

        Args:
            config: Configuration instance
            redis_client: Redis client for caching
            max_queue_size: Maximum message queue size
        """
        self.config = config or WebSocketManagerConfig()
        self.redis = redis_client
        self.max_queue_size = max_queue_size

        # Exchange configurations
        self._exchange_configs: Dict[str, ExchangeWebSocketConfig] = {}

        # Connections
        self._connections: Dict[str, WebSocketConnection] = {}

        # Message queues
        self._message_queues: Dict[str, asyncio.Queue] = {}
        self._message_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_processors: Dict[str, Callable] = {}

        # Metrics
        self._metrics: Dict[str, WebSocketMetrics] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()
        self._running = False

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()

        logger.info("WebSocketManager initialized")

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    async def connect(
        self,
        exchange: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        ssl: bool = True,
        verify_ssl: bool = True,
        subscriptions: Optional[List[Dict[str, Any]]] = None,
        ping_interval: int = 30,
        reconnect_delay: int = 5,
        max_reconnect_attempts: int = 10,
    ) -> bool:
        """
        Connect to an exchange WebSocket.

        Args:
            exchange: Exchange name
            url: WebSocket URL
            headers: HTTP headers
            ssl: Use SSL
            verify_ssl: Verify SSL certificate
            subscriptions: Initial subscriptions
            ping_interval: Ping interval in seconds
            reconnect_delay: Reconnect delay in seconds
            max_reconnect_attempts: Maximum reconnect attempts

        Returns:
            True if connected successfully
        """
        try:
            # Create config
            config = ExchangeWebSocketConfig(
                exchange=exchange,
                url=url,
                headers=headers or {},
                ssl=ssl,
                verify_ssl=verify_ssl,
                subscriptions=subscriptions or [],
                ping_interval=ping_interval,
                reconnect_delay=reconnect_delay,
                max_reconnect_attempts=max_reconnect_attempts,
            )

            self._exchange_configs[exchange] = config

            # Create connection
            connection = WebSocketConnection(
                exchange=exchange,
                state=ConnectionState.CONNECTING,
            )
            self._connections[exchange] = connection

            # Create message queue
            self._message_queues[exchange] = asyncio.Queue(maxsize=self.max_queue_size)

            # Create metrics
            self._metrics[exchange] = WebSocketMetrics(
                exchange=exchange,
                connection_state=ConnectionState.CONNECTING,
            )

            # Establish connection
            await self._establish_connection(exchange)

            logger.info(f"WebSocket connected to {exchange}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to {exchange}: {e}")
            await self._handle_connection_error(exchange, e)
            return False

    async def disconnect(self, exchange: str) -> bool:
        """
        Disconnect from an exchange WebSocket.

        Args:
            exchange: Exchange name

        Returns:
            True if disconnected successfully
        """
        try:
            connection = self._connections.get(exchange)
            if not connection:
                return False

            # Cancel tasks
            if connection.receive_task and not connection.receive_task.done():
                connection.receive_task.cancel()
            if connection.ping_task and not connection.ping_task.done():
                connection.ping_task.cancel()

            # Close socket
            if connection.socket and not connection.socket.closed:
                await connection.socket.close()

            # Close session
            if connection.session and not connection.session.closed:
                await connection.session.close()

            # Update state
            connection.state = ConnectionState.DISCONNECTED
            connection.connected_at = None

            # Update metrics
            if exchange in self._metrics:
                self._metrics[exchange].connection_state = ConnectionState.DISCONNECTED

            logger.info(f"WebSocket disconnected from {exchange}")
            return True

        except Exception as e:
            logger.error(f"Failed to disconnect from {exchange}: {e}")
            return False

    async def subscribe(
        self,
        exchange: str,
        channel: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Subscribe to a channel.

        Args:
            exchange: Exchange name
            channel: Channel name
            params: Subscription parameters

        Returns:
            True if subscribed successfully
        """
        try:
            connection = self._connections.get(exchange)
            if not connection or connection.state != ConnectionState.CONNECTED:
                raise WebSocketConnectionError(f"Not connected to {exchange}")

            # Create subscription message
            subscription_msg = self._create_subscription_message(
                exchange, channel, params or {}
            )

            # Send subscription
            await self._send_message(exchange, subscription_msg)

            # Add to subscriptions
            subscription_key = f"{channel}:{json.dumps(params or {}, sort_keys=True)}"
            connection.subscriptions.add(subscription_key)

            logger.info(f"Subscribed to {channel} on {exchange}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to {channel} on {exchange}: {e}")
            raise WebSocketSubscriptionError(f"Subscription failed: {e}")

    async def unsubscribe(
        self,
        exchange: str,
        channel: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Unsubscribe from a channel.

        Args:
            exchange: Exchange name
            channel: Channel name
            params: Subscription parameters

        Returns:
            True if unsubscribed successfully
        """
        try:
            connection = self._connections.get(exchange)
            if not connection or connection.state != ConnectionState.CONNECTED:
                return False

            # Create unsubscription message
            unsubscription_msg = self._create_unsubscription_message(
                exchange, channel, params or {}
            )

            # Send unsubscription
            await self._send_message(exchange, unsubscription_msg)

            # Remove from subscriptions
            subscription_key = f"{channel}:{json.dumps(params or {}, sort_keys=True)}"
            if subscription_key in connection.subscriptions:
                connection.subscriptions.remove(subscription_key)

            logger.info(f"Unsubscribed from {channel} on {exchange}")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe from {channel} on {exchange}: {e}")
            return False

    async def send_message(
        self,
        exchange: str,
        message: Dict[str, Any],
    ) -> bool:
        """
        Send a message to an exchange.

        Args:
            exchange: Exchange name
            message: Message to send

        Returns:
            True if sent successfully
        """
        try:
            return await self._send_message(exchange, message)
        except Exception as e:
            logger.error(f"Failed to send message to {exchange}: {e}")
            return False

    async def get_next_message(
        self,
        exchange: str,
        timeout: Optional[float] = None,
    ) -> Optional[WebSocketMessage]:
        """
        Get the next message from the queue.

        Args:
            exchange: Exchange name
            timeout: Timeout in seconds

        Returns:
            WebSocketMessage or None
        """
        try:
            queue = self._message_queues.get(exchange)
            if not queue:
                return None

            if timeout:
                message = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                message = await queue.get()

            return message

        except asyncio.TimeoutError:
            raise WebSocketTimeoutError(f"Timeout getting message from {exchange}")
        except Exception as e:
            logger.error(f"Failed to get message from {exchange}: {e}")
            return None

    def register_message_handler(
        self,
        exchange: str,
        message_type: Union[str, MessageType],
        handler: Callable,
    ) -> None:
        """
        Register a message handler.

        Args:
            exchange: Exchange name
            message_type: Message type
            handler: Handler function
        """
        if isinstance(message_type, str):
            message_type = MessageType(message_type)

        self._message_handlers[f"{exchange}:{message_type.value}"].append(handler)

    def register_message_processor(
        self,
        exchange: str,
        processor: Callable,
    ) -> None:
        """
        Register a message processor.

        Args:
            exchange: Exchange name
            processor: Processor function
        """
        self._message_processors[exchange] = processor

    async def get_connection_state(self, exchange: str) -> Optional[ConnectionState]:
        """
        Get connection state for an exchange.

        Args:
            exchange: Exchange name

        Returns:
            ConnectionState or None
        """
        connection = self._connections.get(exchange)
        if connection:
            return connection.state
        return None

    async def get_metrics(self, exchange: Optional[str] = None) -> Dict[str, Any]:
        """
        Get WebSocket metrics.

        Args:
            exchange: Exchange name (all if None)

        Returns:
            Dict of metrics
        """
        if exchange:
            if exchange in self._metrics:
                return self._metrics[exchange].__dict__
            return {}

        return {
            exchange: metrics.__dict__
            for exchange, metrics in self._metrics.items()
        }

    async def clear(self, exchange: Optional[str] = None) -> None:
        """
        Clear WebSocket data.

        Args:
            exchange: Exchange to clear (all if None)
        """
        if exchange:
            await self.disconnect(exchange)
            if exchange in self._message_queues:
                del self._message_queues[exchange]
            if exchange in self._connections:
                del self._connections[exchange]
            if exchange in self._metrics:
                del self._metrics[exchange]
        else:
            for exchange in list(self._connections.keys()):
                await self.disconnect(exchange)
            self._message_queues.clear()
            self._connections.clear()
            self._metrics.clear()

        logger.info(f"WebSocket data cleared for {exchange or 'all'}")

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    async def _establish_connection(self, exchange: str) -> None:
        """Establish WebSocket connection."""
        config = self._exchange_configs.get(exchange)
        if not config:
            raise WebSocketConnectionError(f"No configuration for {exchange}")

        connection = self._connections.get(exchange)
        if not connection:
            raise WebSocketConnectionError(f"No connection for {exchange}")

        try:
            # Create session
            timeout = aiohttp.ClientTimeout(total=30, sock_connect=10)
            connector = aiohttp.TCPConnector(ssl=config.verify_ssl)
            session = ClientSession(
                connector=connector,
                timeout=timeout,
                headers=config.headers,
            )

            # Connect to WebSocket
            socket = await session.ws_connect(
                url=config.url,
                ssl=config.ssl,
                heartbeat=config.heartbeat_interval,
                autoping=False,
                timeout=config.message_timeout,
            )

            # Update connection
            connection.socket = socket
            connection.session = session
            connection.state = ConnectionState.CONNECTED
            connection.connected_at = datetime.utcnow()
            connection.last_message_at = datetime.utcnow()
            connection.reconnect_attempts = 0

            # Update metrics
            if exchange in self._metrics:
                self._metrics[exchange].connection_state = ConnectionState.CONNECTED
                self._metrics[exchange].connected_at = connection.connected_at
                self._metrics[exchange].total_connections += 1
                self._metrics[exchange].successful_connections += 1

            # Start background tasks
            connection.receive_task = asyncio.create_task(
                self._receive_messages(exchange)
            )
            connection.ping_task = asyncio.create_task(
                self._ping_loop(exchange)
            )

            # Send initial subscriptions
            for subscription in config.subscriptions:
                await self.subscribe(
                    exchange,
                    subscription.get('channel', ''),
                    subscription.get('params', {}),
                )

            logger.info(f"WebSocket connection established to {exchange}")

        except Exception as e:
            connection.state = ConnectionState.FAILED
            if exchange in self._metrics:
                self._metrics[exchange].connection_state = ConnectionState.FAILED
                self._metrics[exchange].failed_connections += 1
            raise WebSocketConnectionError(f"Connection failed: {e}")

    async def _receive_messages(self, exchange: str) -> None:
        """Receive messages from WebSocket."""
        connection = self._connections.get(exchange)
        if not connection:
            return

        queue = self._message_queues.get(exchange)
        if not queue:
            return

        while connection.state in [ConnectionState.CONNECTED, ConnectionState.RECONNECTING]:
            try:
                if not connection.socket:
                    break

                msg = await connection.socket.receive()

                if msg.type == WSMsgType.TEXT:
                    await self._process_text_message(exchange, msg.data)
                elif msg.type == WSMsgType.BINARY:
                    await self._process_binary_message(exchange, msg.data)
                elif msg.type == WSMsgType.CLOSE:
                    logger.info(f"WebSocket closed for {exchange}")
                    break
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error for {exchange}: {msg.data}")
                    break
                elif msg.type == WSMsgType.PING:
                    await self._handle_ping(exchange)
                elif msg.type == WSMsgType.PONG:
                    await self._handle_pong(exchange)

                connection.last_message_at = datetime.utcnow()
                connection.messages_received += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving message from {exchange}: {e}")
                connection.errors += 1

                if connection.state == ConnectionState.CONNECTED:
                    await self._handle_connection_error(exchange, e)

    async def _process_text_message(self, exchange: str, data: str) -> None:
        """Process text message."""
        try:
            # Parse JSON
            json_data = json.loads(data)

            # Determine message type
            msg_type = self._determine_message_type(exchange, json_data)

            # Create message
            message = WebSocketMessage(
                exchange=exchange,
                type=msg_type,
                data=json_data,
            )

            # Process message
            await self._process_message(exchange, message)

            # Queue message
            queue = self._message_queues.get(exchange)
            if queue:
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    logger.warning(f"Message queue full for {exchange}, dropping message")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {exchange}: {e}")
        except Exception as e:
            logger.error(f"Error processing message from {exchange}: {e}")

    async def _process_binary_message(self, exchange: str, data: bytes) -> None:
        """Process binary message."""
        try:
            # Try to decode as JSON
            try:
                json_data = json.loads(data.decode('utf-8'))
                await self._process_text_message(exchange, json_data)
                return
            except:
                pass

            # Binary message
            message = WebSocketMessage(
                exchange=exchange,
                type=MessageType.UNKNOWN,
                data={'binary': data.hex()},
            )

            await self._process_message(exchange, message)

            queue = self._message_queues.get(exchange)
            if queue:
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    logger.warning(f"Message queue full for {exchange}, dropping binary message")

        except Exception as e:
            logger.error(f"Error processing binary message from {exchange}: {e}")

    async def _process_message(self, exchange: str, message: WebSocketMessage) -> None:
        """Process a message."""
        try:
            # Call message processor
            processor = self._message_processors.get(exchange)
            if processor:
                if asyncio.iscoroutinefunction(processor):
                    await processor(message)
                else:
                    processor(message)

            # Call message handlers
            key = f"{exchange}:{message.type.value}"
            handlers = self._message_handlers.get(key, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    logger.error(f"Error in handler: {e}")

            message.processed = True

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            message.error = str(e)

    async def _send_message(self, exchange: str, message: Dict[str, Any]) -> bool:
        """Send a message."""
        connection = self._connections.get(exchange)
        if not connection or connection.state != ConnectionState.CONNECTED:
            raise WebSocketConnectionError(f"Not connected to {exchange}")

        try:
            await connection.socket.send_json(message)
            connection.messages_sent += 1
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {exchange}: {e}")
            raise WebSocketMessageError(f"Send failed: {e}")

    async def _ping_loop(self, exchange: str) -> None:
        """Send periodic ping messages."""
        connection = self._connections.get(exchange)
        if not connection:
            return

        config = self._exchange_configs.get(exchange)
        if not config:
            return

        while connection.state == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(config.ping_interval)

                # Send ping
                await self._send_ping(exchange)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ping loop for {exchange}: {e}")

    async def _send_ping(self, exchange: str) -> None:
        """Send a ping message."""
        try:
            ping_message = self._create_ping_message(exchange)
            await self._send_message(exchange, ping_message)
            connection = self._connections.get(exchange)
            if connection:
                connection.last_heartbeat_at = datetime.utcnow()
        except Exception as e:
            logger.warning(f"Failed to send ping to {exchange}: {e}")

    async def _handle_ping(self, exchange: str) -> None:
        """Handle ping message."""
        try:
            pong_message = self._create_pong_message(exchange)
            await self._send_message(exchange, pong_message)
        except Exception as e:
            logger.warning(f"Failed to handle ping from {exchange}: {e}")

    async def _handle_pong(self, exchange: str) -> None:
        """Handle pong message."""
        connection = self._connections.get(exchange)
        if connection:
            connection.last_heartbeat_at = datetime.utcnow()

    async def _handle_connection_error(self, exchange: str, error: Exception) -> None:
        """Handle connection error."""
        connection = self._connections.get(exchange)
        if not connection:
            return

        config = self._exchange_configs.get(exchange)
        if not config:
            return

        # Update state
        connection.state = ConnectionState.RECONNECTING
        connection.reconnect_attempts += 1

        if exchange in self._metrics:
            self._metrics[exchange].connection_state = ConnectionState.RECONNECTING
            self._metrics[exchange].failed_connections += 1

        # Check max attempts
        if connection.reconnect_attempts > config.max_reconnect_attempts:
            connection.state = ConnectionState.FAILED
            logger.error(f"Max reconnect attempts reached for {exchange}")
            return

        # Calculate backoff
        delay = min(
            config.reconnect_delay * (2 ** (connection.reconnect_attempts - 1)),
            60,  # Max delay
        )

        logger.info(
            f"Reconnecting to {exchange} in {delay}s "
            f"(attempt {connection.reconnect_attempts}/{config.max_reconnect_attempts})"
        )

        # Wait and reconnect
        await asyncio.sleep(delay)

        try:
            await self._establish_connection(exchange)
            connection.reconnect_attempts = 0
            if exchange in self._metrics:
                self._metrics[exchange].total_reconnections += 1
        except Exception as e:
            logger.error(f"Reconnect failed for {exchange}: {e}")

    def _determine_message_type(
        self,
        exchange: str,
        data: Dict[str, Any],
    ) -> MessageType:
        """Determine message type."""
        # Exchange-specific message type detection
        if exchange in ['binance', 'bybit', 'okx']:
            if 'data' in data:
                return MessageType.PRICE
            if 'e' in data:
                event = data.get('e', '')
                if event in ['24hrTicker', 'ticker']:
                    return MessageType.TICKER
                if event in ['depthUpdate', 'orderBook']:
                    return MessageType.ORDER_BOOK
                if event == 'trade':
                    return MessageType.TRADE
                if event == 'kline':
                    return MessageType.CANDLE
            if 'ping' in data:
                return MessageType.PING
            if 'pong' in data:
                return MessageType.PONG
            if 'result' in data:
                return MessageType.SUBSCRIPTION

        elif exchange in ['coinbase', 'kraken']:
            if 'type' in data:
                msg_type = data.get('type', '')
                if msg_type == 'ticker':
                    return MessageType.TICKER
                if msg_type == 'match':
                    return MessageType.TRADE
                if msg_type == 'l2update':
                    return MessageType.ORDER_BOOK
                if msg_type == 'heartbeat':
                    return MessageType.HEARTBEAT
                if msg_type == 'subscriptions':
                    return MessageType.SUBSCRIPTION

        # Generic detection
        if 'price' in data or 'p' in data:
            return MessageType.PRICE
        if 'ticker' in data:
            return MessageType.TICKER
        if 'order_book' in data or 'orderBook' in data:
            return MessageType.ORDER_BOOK
        if 'trade' in data:
            return MessageType.TRADE
        if 'candle' in data or 'kline' in data:
            return MessageType.CANDLE
        if 'ping' in data:
            return MessageType.PING
        if 'pong' in data:
            return MessageType.PONG

        return MessageType.UNKNOWN

    def _create_ping_message(self, exchange: str) -> Dict[str, Any]:
        """Create a ping message."""
        # Exchange-specific ping messages
        if exchange == 'binance':
            return {'ping': int(time.time() * 1000)}
        elif exchange == 'bybit':
            return {'op': 'ping'}
        elif exchange == 'okx':
            return {'op': 'ping'}
        elif exchange == 'coinbase':
            return {'type': 'ping'}
        elif exchange == 'kraken':
            return {'event': 'ping'}
        elif exchange == 'bitget':
            return {'op': 'ping'}
        elif exchange == 'gateio':
            return {'method': 'server.ping', 'id': int(time.time())}
        else:
            return {'type': 'ping', 'timestamp': time.time()}

    def _create_pong_message(self, exchange: str) -> Dict[str, Any]:
        """Create a pong message."""
        # Exchange-specific pong messages
        if exchange == 'binance':
            return {'pong': int(time.time() * 1000)}
        elif exchange == 'bybit':
            return {'op': 'pong'}
        elif exchange == 'okx':
            return {'op': 'pong'}
        elif exchange == 'coinbase':
            return {'type': 'pong'}
        elif exchange == 'kraken':
            return {'event': 'pong'}
        elif exchange == 'bitget':
            return {'op': 'pong'}
        elif exchange == 'gateio':
            return {'method': 'server.pong', 'id': int(time.time())}
        else:
            return {'type': 'pong', 'timestamp': time.time()}

    def _create_subscription_message(
        self,
        exchange: str,
        channel: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a subscription message."""
        # Exchange-specific subscription messages
        if exchange == 'binance':
            return {
                'method': 'SUBSCRIBE',
                'params': [self._format_binance_channel(channel, params)],
                'id': int(time.time() * 1000),
            }
        elif exchange == 'bybit':
            return {
                'op': 'subscribe',
                'args': [self._format_bybit_channel(channel, params)],
            }
        elif exchange == 'okx':
            return {
                'op': 'subscribe',
                'args': [self._format_okx_channel(channel, params)],
            }
        elif exchange == 'coinbase':
            return {
                'type': 'subscribe',
                'product_ids': params.get('symbols', []),
                'channels': [channel],
            }
        elif exchange == 'kraken':
            return {
                'event': 'subscribe',
                'subscription': {'name': channel},
                'pair': params.get('symbols', []),
            }
        else:
            return {
                'type': 'subscribe',
                'channel': channel,
                'params': params,
            }

    def _create_unsubscription_message(
        self,
        exchange: str,
        channel: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create an unsubscription message."""
        # Exchange-specific unsubscription messages
        if exchange == 'binance':
            return {
                'method': 'UNSUBSCRIBE',
                'params': [self._format_binance_channel(channel, params)],
                'id': int(time.time() * 1000),
            }
        elif exchange == 'bybit':
            return {
                'op': 'unsubscribe',
                'args': [self._format_bybit_channel(channel, params)],
            }
        elif exchange == 'okx':
            return {
                'op': 'unsubscribe',
                'args': [self._format_okx_channel(channel, params)],
            }
        elif exchange == 'coinbase':
            return {
                'type': 'unsubscribe',
                'product_ids': params.get('symbols', []),
                'channels': [channel],
            }
        elif exchange == 'kraken':
            return {
                'event': 'unsubscribe',
                'subscription': {'name': channel},
                'pair': params.get('symbols', []),
            }
        else:
            return {
                'type': 'unsubscribe',
                'channel': channel,
                'params': params,
            }

    def _format_binance_channel(self, channel: str, params: Dict[str, Any]) -> str:
        """Format Binance channel."""
        symbols = params.get('symbols', [])
        symbol = symbols[0] if symbols else ''
        if channel == 'ticker':
            return f"{symbol.lower()}@ticker"
        elif channel == 'depth':
            level = params.get('level', 20)
            return f"{symbol.lower()}@depth{level}"
        elif channel == 'trade':
            return f"{symbol.lower()}@trade"
        elif channel == 'kline':
            interval = params.get('interval', '1m')
            return f"{symbol.lower()}@kline_{interval}"
        else:
            return f"{symbol.lower()}@{channel}"

    def _format_bybit_channel(self, channel: str, params: Dict[str, Any]) -> str:
        """Format Bybit channel."""
        symbols = params.get('symbols', [])
        symbol = symbols[0] if symbols else ''
        if channel == 'ticker':
            return f"tickers.{symbol}"
        elif channel == 'depth':
            return f"orderbook.200.{symbol}"
        elif channel == 'trade':
            return f"trade.{symbol}"
        elif channel == 'kline':
            interval = params.get('interval', '1')
            return f"kline.{interval}.{symbol}"
        else:
            return f"{channel}.{symbol}"

    def _format_okx_channel(self, channel: str, params: Dict[str, Any]) -> str:
        """Format OKX channel."""
        symbols = params.get('symbols', [])
        symbol = symbols[0] if symbols else ''
        if channel == 'ticker':
            return f"tickers:{symbol}"
        elif channel == 'depth':
            return f"books:{symbol}"
        elif channel == 'trade':
            return f"trades:{symbol}"
        elif channel == 'candle':
            interval = params.get('interval', '1m')
            return f"candle{interval}:{symbol}"
        else:
            return f"{channel}:{symbol}"

    # ============================================================
    # CONTEXT MANAGER METHODS
    # ============================================================

    async def start(self) -> None:
        """Start the WebSocket manager."""
        self._running = True
        logger.info("WebSocketManager started")

    async def stop(self) -> None:
        """Stop the WebSocket manager."""
        self._running = False

        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        # Disconnect all
        for exchange in list(self._connections.keys()):
            await self.disconnect(exchange)

        await self.clear()

        logger.info("WebSocketManager stopped")

    async def __aenter__(self) -> 'WebSocketManager':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_websocket_manager(
    config: Optional[WebSocketManagerConfig] = None,
    redis_client: Optional[Any] = None,
    max_queue_size: int = 10000,
) -> WebSocketManager:
    """
    Create a WebSocket manager instance.

    Args:
        config: Configuration instance
        redis_client: Redis client for caching
        max_queue_size: Maximum message queue size

    Returns:
        WebSocketManager instance
    """
    return WebSocketManager(
        config=config,
        redis_client=redis_client,
        max_queue_size=max_queue_size,
    )


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the WebSocket manager.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        # Initialize WebSocket manager
        ws_manager = create_websocket_manager()

        # Connect to Binance WebSocket
        await ws_manager.connect(
            exchange="binance",
            url="wss://stream.binance.com:9443/ws",
            subscriptions=[
                {'channel': 'ticker', 'params': {'symbols': ['btcusdt']}},
                {'channel': 'depth', 'params': {'symbols': ['btcusdt'], 'level': 20}},
            ],
        )

        # Register message handler
        def handle_price(message: WebSocketMessage):
            if message.type == MessageType.PRICE:
                print(f"Price update: {message.data}")

        ws_manager.register_message_handler("binance", MessageType.PRICE, handle_price)

        # Process messages
        try:
            while True:
                message = await ws_manager.get_next_message("binance", timeout=5)
                if message:
                    print(f"Received: {message.type} from {message.exchange}")
        except KeyboardInterrupt:
            pass

        # Disconnect
        await ws_manager.disconnect("binance")
        await ws_manager.stop()

    asyncio.run(main())
