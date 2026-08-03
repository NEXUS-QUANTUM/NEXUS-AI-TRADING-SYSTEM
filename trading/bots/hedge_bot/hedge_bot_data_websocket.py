# trading/bots/hedge_bot/hedge_bot_data_websocket.py

import asyncio
import logging
import time
import json
import hashlib
import base64
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import websockets
import aiohttp
import ssl
import certifi

logger = logging.getLogger(__name__)


class WebSocketType(str, Enum):
    MARKET = "market"
    ORDER = "order"
    TRADE = "trade"
    POSITION = "position"
    PORTFOLIO = "portfolio"
    SIGNAL = "signal"
    ALERT = "alert"
    SYSTEM = "system"
    CHAT = "chat"
    STREAM = "stream"


class WebSocketStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    CLOSED = "closed"
    PAUSED = "paused"


class WebSocketCompression(str, Enum):
    NONE = "none"
    PERMESSAGE_DEFLATE = "permessage_deflate"
    ZLIB = "zlib"


@dataclass
class WebSocketConfig:
    id: str
    name: str
    type: WebSocketType
    url: str
    auth_token: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    compression: WebSocketCompression = WebSocketCompression.NONE
    reconnect_attempts: int = 5
    reconnect_delay: float = 1.0
    ping_interval: float = 30.0
    ping_timeout: float = 10.0
    max_message_size: int = 1024 * 1024 * 10
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebSocketMessage:
    id: str
    connection_id: str
    data: Any
    type: str
    timestamp: float
    compressed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebSocketConnection:
    id: str
    config_id: str
    status: WebSocketStatus
    endpoint: str
    connected_at: Optional[float] = None
    last_message: Optional[float] = None
    messages_received: int = 0
    messages_sent: int = 0
    errors: int = 0
    reconnect_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebSocketSubscription:
    id: str
    connection_id: str
    channel: str
    params: Dict[str, Any]
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class WebSocketManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._connections: Dict[str, WebSocketConnection] = {}
        self._configs: Dict[str, WebSocketConfig] = {}
        self._subscriptions: Dict[str, WebSocketSubscription] = {}
        self._message_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._observers: List[Callable] = []
        self._websockets: Dict[str, websockets.WebSocketClientProtocol] = {}
        self._reconnect_tasks: Dict[str, asyncio.Task] = {}
        self._ping_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._ssl_context = None
        
        self._initialize_ssl_context()

    def _initialize_ssl_context(self) -> None:
        try:
            self._ssl_context = ssl.create_default_context(cafile=certifi.where())
        except:
            self._ssl_context = ssl.create_default_context()

    def register_handler(self, message_type: str, handler: Callable) -> None:
        self._message_handlers[message_type].append(handler)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_config(
        self,
        name: str,
        type: WebSocketType,
        url: str,
        auth_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        compression: WebSocketCompression = WebSocketCompression.NONE,
        reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
        ping_interval: float = 30.0,
        ping_timeout: float = 10.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> WebSocketConfig:
        async with self._lock:
            config_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            config = WebSocketConfig(
                id=config_id,
                name=name,
                type=type,
                url=url,
                auth_token=auth_token,
                headers=headers or {},
                compression=compression,
                reconnect_attempts=reconnect_attempts,
                reconnect_delay=reconnect_delay,
                ping_interval=ping_interval,
                ping_timeout=ping_timeout,
                metadata=metadata or {}
            )
            
            self._configs[config_id] = config
            await self._notify_observers("config_created", config)
            return config

    async def connect(self, config_id: str) -> Optional[str]:
        async with self._lock:
            if config_id not in self._configs:
                return None
            
            config = self._configs[config_id]
            
            connection_id = hashlib.md5(f"{config_id}_{time.time()}".encode()).hexdigest()
            
            connection = WebSocketConnection(
                id=connection_id,
                config_id=config_id,
                status=WebSocketStatus.CONNECTING,
                endpoint=config.url,
                metadata=config.metadata
            )
            
            self._connections[connection_id] = connection
            await self._notify_observers("connection_created", connection)
            
            try:
                headers = config.headers.copy()
                if config.auth_token:
                    headers["Authorization"] = f"Bearer {config.auth_token}"
                
                extra_headers = [(k, v) for k, v in headers.items()]
                
                ws = await websockets.connect(
                    config.url,
                    extra_headers=extra_headers,
                    compression=self._get_compression(config.compression),
                    max_size=config.max_message_size,
                    ping_interval=config.ping_interval,
                    ping_timeout=config.ping_timeout,
                    ssl=self._ssl_context
                )
                
                self._websockets[connection_id] = ws
                connection.status = WebSocketStatus.CONNECTED
                connection.connected_at = time.time()
                connection.reconnect_count = 0
                
                self._ping_tasks[connection_id] = asyncio.create_task(
                    self._ping_loop(connection_id)
                )
                
                asyncio.create_task(self._receive_loop(connection_id))
                
                await self._notify_observers("connection_established", connection)
                return connection_id
                
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                connection.status = WebSocketStatus.ERROR
                connection.errors += 1
                await self._notify_observers("connection_failed", connection, str(e))
                return None

    async def _receive_loop(self, connection_id: str) -> None:
        connection = self._connections.get(connection_id)
        ws = self._websockets.get(connection_id)
        
        if not connection or not ws:
            return
        
        while connection.status in [WebSocketStatus.CONNECTED, WebSocketStatus.CONNECTING]:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                
                if message is None:
                    continue
                
                await self._process_message(connection_id, message)
                
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed:
                await self._handle_disconnect(connection_id)
                break
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                connection.errors += 1
                await asyncio.sleep(1)

    async def _process_message(self, connection_id: str, message: Any) -> None:
        connection = self._connections.get(connection_id)
        if not connection:
            return
        
        try:
            if isinstance(message, bytes):
                if connection.config_id in self._configs:
                    config = self._configs[connection.config_id]
                    if config.compression == WebSocketCompression.ZLIB:
                        message = zlib.decompress(message)
                message = message.decode('utf-8')
            
            data = json.loads(message)
            
            msg_id = hashlib.md5(f"{connection_id}_{time.time()}".encode()).hexdigest()
            
            ws_message = WebSocketMessage(
                id=msg_id,
                connection_id=connection_id,
                data=data,
                type=data.get("type", "unknown"),
                timestamp=time.time(),
                compressed=False
            )
            
            connection.last_message = ws_message.timestamp
            connection.messages_received += 1
            
            await self._notify_observers("message_received", ws_message)
            
            handlers = self._message_handlers.get(ws_message.type, [])
            handlers.extend(self._message_handlers.get("all", []))
            
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(ws_message)
                    else:
                        handler(ws_message)
                except Exception as e:
                    logger.error(f"Handler error for {ws_message.type}: {e}")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Message processing error: {e}")

    async def _ping_loop(self, connection_id: str) -> None:
        connection = self._connections.get(connection_id)
        ws = self._websockets.get(connection_id)
        
        if not connection or not ws:
            return
        
        while connection.status == WebSocketStatus.CONNECTED:
            try:
                await asyncio.sleep(connection.config.ping_interval)
                await ws.ping()
                await self._notify_observers("ping_sent", connection_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ping error: {e}")
                await self._handle_disconnect(connection_id)
                break

    async def _handle_disconnect(self, connection_id: str) -> None:
        connection = self._connections.get(connection_id)
        if not connection:
            return
        
        connection.status = WebSocketStatus.DISCONNECTED
        await self._notify_observers("disconnected", connection_id)
        
        if connection_id in self._ping_tasks:
            self._ping_tasks[connection_id].cancel()
            del self._ping_tasks[connection_id]
        
        if connection_id in self._websockets:
            del self._websockets[connection_id]
        
        if connection.reconnect_count < connection.config.reconnect_attempts:
            connection.status = WebSocketStatus.RECONNECTING
            connection.reconnect_count += 1
            await self._notify_observers("reconnecting", connection)
            
            delay = connection.config.reconnect_delay * (2 ** (connection.reconnect_count - 1))
            await asyncio.sleep(delay)
            
            await self.connect(connection.config_id)
        else:
            connection.status = WebSocketStatus.CLOSED
            await self._notify_observers("connection_closed", connection)

    async def send_message(
        self,
        connection_id: str,
        data: Any,
        message_type: str = "message"
    ) -> Optional[str]:
        async with self._lock:
            if connection_id not in self._connections:
                return None
            
            connection = self._connections[connection_id]
            ws = self._websockets.get(connection_id)
            
            if not ws or connection.status != WebSocketStatus.CONNECTED:
                return None
            
            try:
                message = {
                    "id": hashlib.md5(f"{connection_id}_{time.time()}".encode()).hexdigest(),
                    "type": message_type,
                    "timestamp": time.time(),
                    "data": data
                }
                
                json_message = json.dumps(message)
                
                if connection_id in self._configs:
                    config = self._configs[connection.config_id]
                    if config.compression == WebSocketCompression.ZLIB:
                        json_message = zlib.compress(json_message.encode())
                
                await ws.send(json_message)
                
                connection.messages_sent += 1
                await self._notify_observers("message_sent", message)
                
                return message["id"]
                
            except Exception as e:
                logger.error(f"Send message error: {e}")
                return None

    async def subscribe(
        self,
        connection_id: str,
        channel: str,
        params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        async with self._lock:
            if connection_id not in self._connections:
                return None
            
            subscription_id = hashlib.md5(f"{connection_id}_{channel}_{time.time()}".encode()).hexdigest()
            
            subscription = WebSocketSubscription(
                id=subscription_id,
                connection_id=connection_id,
                channel=channel,
                params=params or {},
                metadata=metadata or {}
            )
            
            self._subscriptions[subscription_id] = subscription
            
            await self.send_message(
                connection_id,
                {
                    "action": "subscribe",
                    "channel": channel,
                    "params": params or {}
                },
                "subscription"
            )
            
            await self._notify_observers("subscribed", subscription)
            return subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        async with self._lock:
            if subscription_id not in self._subscriptions:
                return False
            
            subscription = self._subscriptions[subscription_id]
            subscription.active = False
            
            await self.send_message(
                subscription.connection_id,
                {
                    "action": "unsubscribe",
                    "channel": subscription.channel
                },
                "subscription"
            )
            
            await self._notify_observers("unsubscribed", subscription)
            return True

    async def disconnect(self, connection_id: str) -> bool:
        async with self._lock:
            if connection_id not in self._connections:
                return False
            
            connection = self._connections[connection_id]
            ws = self._websockets.get(connection_id)
            
            if ws:
                await ws.close()
            
            connection.status = WebSocketStatus.CLOSED
            
            if connection_id in self._ping_tasks:
                self._ping_tasks[connection_id].cancel()
                del self._ping_tasks[connection_id]
            
            if connection_id in self._websockets:
                del self._websockets[connection_id]
            
            await self._notify_observers("disconnected", connection_id)
            return True

    def _get_compression(self, compression: WebSocketCompression) -> Optional[str]:
        if compression == WebSocketCompression.PERMESSAGE_DEFLATE:
            return "permessage-deflate"
        elif compression == WebSocketCompression.NONE:
            return None
        else:
            return None

    async def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        return self._connections.get(connection_id)

    async def get_connections(self) -> List[WebSocketConnection]:
        return list(self._connections.values())

    async def get_config(self, config_id: str) -> Optional[WebSocketConfig]:
        return self._configs.get(config_id)

    async def get_subscription(self, subscription_id: str) -> Optional[WebSocketSubscription]:
        return self._subscriptions.get(subscription_id)

    async def get_subscriptions(self, connection_id: str) -> List[WebSocketSubscription]:
        return [s for s in self._subscriptions.values() if s.connection_id == connection_id]

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
        return {
            "connections": len(self._connections),
            "configs": len(self._configs),
            "subscriptions": len(self._subscriptions),
            "active_connections": len([c for c in self._connections.values() if c.status == WebSocketStatus.CONNECTED]),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "WebSocketType",
    "WebSocketStatus",
    "WebSocketCompression",
    "WebSocketConfig",
    "WebSocketMessage",
    "WebSocketConnection",
    "WebSocketSubscription",
    "WebSocketManager"
]
