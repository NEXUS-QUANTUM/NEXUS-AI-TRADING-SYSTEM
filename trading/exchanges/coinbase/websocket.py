"""
NEXUS AI TRADING SYSTEM - Coinbase WebSocket Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/coinbase/websocket.py
Description: Coinbase WebSocket streaming with full API integration
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict

import aiohttp
import websockets
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status, WebSocket, WebSocketDisconnect

# NEXUS Internal Imports
from shared.configs.exchange_config import ExchangeConfig
from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async
from shared.utilities.websocket_manager import WebSocketManager

# Coinbase imports
from trading.exchanges.coinbase.base import (
    CoinbaseBase,
    CoinbaseEnvironment,
    CoinbaseGranularity,
    CoinbaseWebSocketChannel
)
from trading.exchanges.coinbase.exceptions import (
    CoinbaseException,
    CoinbaseErrorCode,
    CoinbaseErrorHandler
)
from trading.exchanges.coinbase.converter import CoinbaseConverter

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class CoinbaseStreamType(str, Enum):
    """Coinbase stream types"""
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    TICKER = "ticker"
    LEVEL2 = "level2"
    USER = "user"
    MATCHES = "matches"
    FULL = "full"


class CoinbaseStreamAction(str, Enum):
    """Coinbase stream actions"""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    PONG = "pong"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CoinbaseStreamMessage(BaseModel):
    """Coinbase stream message"""
    channel: str
    data: Dict[str, Any]
    timestamp: datetime


class CoinbaseStreamSubscription(BaseModel):
    """Coinbase stream subscription"""
    stream_name: str
    product_id: str
    channel: str
    params: Optional[Dict[str, Any]] = None
    callback: Optional[Callable] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CoinbaseWebSocketConnection:
    """Coinbase WebSocket connection"""
    connection_id: str
    url: str
    websocket: websockets.WebSocketClientProtocol
    subscriptions: List[str]
    connected_at: datetime
    last_heartbeat: datetime
    active: bool


@dataclass
class CoinbaseStreamEvent:
    """Coinbase stream event"""
    event_type: str
    product_id: str
    data: Dict[str, Any]
    timestamp: datetime
    raw_data: Dict[str, Any]


# =============================================================================
# COINBASE WEBSOCKET
# =============================================================================

class CoinbaseWebSocket:
    """
    Coinbase WebSocket Streaming with full API integration.
    
    Features:
    - Multiple stream types (heartbeat, status, ticker, level2, user, matches, full)
    - Automatic reconnection
    - Heartbeat management
    - Subscription management
    - Event handling
    - Multiple connection support
    - Data conversion
    - Error handling
    - Public and private streams
    """

    PRODUCTION_WS_URL = "wss://ws-feed.exchange.coinbase.com"
    SANDBOX_WS_URL = "wss://ws-feed-public.sandbox.exchange.coinbase.com"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        environment: CoinbaseEnvironment = CoinbaseEnvironment.SANDBOX,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize CoinbaseWebSocket.
        
        Args:
            api_key: Coinbase API key
            api_secret: Coinbase API secret
            passphrase: Coinbase passphrase
            environment: Coinbase environment
            config: Exchange configuration
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.environment = environment
        self.config = config or ExchangeConfig()
        
        # WebSocket URL
        self.ws_url = self._get_ws_url()
        
        # Connections
        self._connections: Dict[str, CoinbaseWebSocketConnection] = {}
        self._connection_counter: int = 0
        
        # Subscriptions
        self._subscriptions: Dict[str, List[CoinbaseStreamSubscription]] = defaultdict(list)
        self._subscription_counters: Dict[str, int] = defaultdict(int)
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._stream_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Converter
        self.converter = CoinbaseConverter()
        
        # Error handler
        self._error_handler = CoinbaseErrorHandler()
        
        # State
        self._is_running: bool = False
        self._reconnect_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info(f"CoinbaseWebSocket initialized in {environment.value}")

    def _get_ws_url(self) -> str:
        """Get WebSocket URL based on environment"""
        if self.environment == CoinbaseEnvironment.SANDBOX:
            return self.SANDBOX_WS_URL
        return self.PRODUCTION_WS_URL

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(
        self,
        stream_key: Optional[str] = None,
        is_private: bool = False
    ) -> str:
        """
        Connect to WebSocket.
        
        Args:
            stream_key: Stream key
            is_private: Whether this is a private connection
            
        Returns:
            str: Connection ID
        """
        try:
            # Connect
            ws = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            # Create connection
            self._connection_counter += 1
            connection_id = f"ws_{self._connection_counter}_{int(time.time())}"
            
            connection = CoinbaseWebSocketConnection(
                connection_id=connection_id,
                url=self.ws_url,
                websocket=ws,
                subscriptions=[],
                connected_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow(),
                active=True
            )
            
            self._connections[connection_id] = connection
            
            # Authenticate if private
            if is_private:
                if not self.api_key or not self.api_secret or not self.passphrase:
                    raise ValueError("API key, secret, and passphrase required for private connection")
                
                await self._authenticate(connection_id)
            
            # Start receive loop
            asyncio.create_task(self._receive_loop(connection_id))
            
            logger.info(f"WebSocket connected: {connection_id}")
            return connection_id
            
        except Exception as e:
            logger.error(f"Error connecting to WebSocket: {e}")
            raise

    async def _authenticate(self, connection_id: str) -> None:
        """
        Authenticate private WebSocket connection.
        
        Args:
            connection_id: Connection ID
        """
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        
        # Generate authentication payload
        timestamp = str(int(time.time()))
        message = f"{timestamp}GET"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Send authentication request
        auth_msg = {
            "type": "subscribe",
            "product_ids": [],
            "channels": [{
                "name": "user",
                "product_ids": []
            }],
            "signature": signature,
            "key": self.api_key,
            "passphrase": self.passphrase,
            "timestamp": timestamp
        }
        
        await connection.websocket.send(json.dumps(auth_msg))
        logger.info(f"Authentication request sent for {connection_id}")

    async def disconnect(self, connection_id: str) -> None:
        """
        Disconnect WebSocket.
        
        Args:
            connection_id: Connection ID
        """
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        connection.active = False
        
        try:
            await connection.websocket.close()
        except Exception as e:
            logger.warning(f"Error closing WebSocket: {e}")
        
        # Clean up subscriptions
        if connection_id in self._subscriptions:
            del self._subscriptions[connection_id]
        
        del self._connections[connection_id]
        
        logger.info(f"WebSocket disconnected: {connection_id}")

    async def disconnect_all(self) -> None:
        """Disconnect all WebSockets"""
        for connection_id in list(self._connections.keys()):
            await self.disconnect(connection_id)

    async def _receive_loop(self, connection_id: str) -> None:
        """Receive messages from WebSocket"""
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        
        try:
            async for message in connection.websocket:
                if not connection.active:
                    break
                
                await self._handle_message(connection_id, message)
                connection.last_heartbeat = datetime.utcnow()
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"WebSocket connection closed: {connection_id}")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
        
        # Clean up on disconnect
        if connection.active:
            await self.reconnect(connection_id)

    async def _handle_message(
        self,
        connection_id: str,
        message: Union[str, bytes]
    ) -> None:
        """Handle incoming message"""
        try:
            # Parse message
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            
            data = json.loads(message)
            
            # Check for heartbeat
            if data.get('type') == 'heartbeat':
                await self._send_pong(connection_id)
                return
            
            # Process event
            await self._process_event(connection_id, data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def _send_pong(self, connection_id: str) -> None:
        """Send pong response"""
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        pong_msg = {"type": "pong"}
        await connection.websocket.send(json.dumps(pong_msg))

    # =========================================================================
    # Subscription Management
    # =========================================================================

    async def subscribe(
        self,
        product_ids: List[str],
        channels: List[str],
        params: Optional[Dict[str, Any]] = None,
        connection_id: Optional[str] = None,
        is_private: bool = False
    ) -> str:
        """
        Subscribe to streams.
        
        Args:
            product_ids: List of product IDs
            channels: List of channels
            params: Additional parameters
            connection_id: Connection ID
            is_private: Whether this is a private subscription
            
        Returns:
            str: Connection ID
        """
        try:
            # Build subscription message
            subscribe_msg = {
                "type": "subscribe",
                "product_ids": product_ids,
                "channels": channels
            }
            
            # Add authentication if private
            if is_private:
                if not self.api_key or not self.api_secret or not self.passphrase:
                    raise ValueError("API key, secret, and passphrase required for private subscription")
                
                timestamp = str(int(time.time()))
                message = f"{timestamp}GET"
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    message.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                subscribe_msg['signature'] = signature
                subscribe_msg['key'] = self.api_key
                subscribe_msg['passphrase'] = self.passphrase
                subscribe_msg['timestamp'] = timestamp
            
            # Connect if no connection
            if not connection_id:
                connection_id = await self.connect(is_private=is_private)
            
            # Send subscription
            await self._send_subscribe(connection_id, subscribe_msg)
            
            # Store subscriptions
            for product_id in product_ids:
                for channel in channels:
                    subscription = CoinbaseStreamSubscription(
                        stream_name=f"{product_id}_{channel}",
                        product_id=product_id,
                        channel=channel,
                        params=params
                    )
                    self._subscriptions[connection_id].append(subscription)
                    self._subscription_counters[f"{product_id}_{channel}"] += 1
            
            logger.info(f"Subscribed to {len(channels)} streams for {product_ids}")
            return connection_id
            
        except Exception as e:
            logger.error(f"Error subscribing: {e}")
            raise

    async def unsubscribe(
        self,
        product_ids: List[str],
        channels: List[str],
        connection_id: str
    ) -> None:
        """
        Unsubscribe from streams.
        
        Args:
            product_ids: List of product IDs
            channels: List of channels
            connection_id: Connection ID
        """
        try:
            # Build unsubscription message
            unsubscribe_msg = {
                "type": "unsubscribe",
                "product_ids": product_ids,
                "channels": channels
            }
            
            # Send unsubscription
            await self._send_unsubscribe(connection_id, unsubscribe_msg)
            
            # Remove subscriptions
            if connection_id in self._subscriptions:
                self._subscriptions[connection_id] = [
                    s for s in self._subscriptions[connection_id]
                    if s.product_id not in product_ids or s.channel not in channels
                ]
            
            logger.info(f"Unsubscribed from {len(channels)} streams for {product_ids}")
            
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
            raise

    async def _send_subscribe(
        self,
        connection_id: str,
        message: Dict[str, Any]
    ) -> None:
        """Send subscription request"""
        if connection_id not in self._connections:
            raise ValueError(f"Connection {connection_id} not found")
        
        connection = self._connections[connection_id]
        await connection.websocket.send(json.dumps(message))
        logger.debug(f"Sent subscription: {message.get('channels')}")

    async def _send_unsubscribe(
        self,
        connection_id: str,
        message: Dict[str, Any]
    ) -> None:
        """Send unsubscription request"""
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        await connection.websocket.send(json.dumps(message))
        logger.debug(f"Sent unsubscription: {message.get('channels')}")

    # =========================================================================
    # Event Handling
    # =========================================================================

    async def _process_event(
        self,
        connection_id: str,
        data: Dict[str, Any]
    ) -> None:
        """Process event"""
        try:
            # Determine event type and product_id
            event_type = data.get('type', 'unknown')
            product_id = data.get('product_id', '')
            
            # Create event
            event = CoinbaseStreamEvent(
                event_type=event_type,
                product_id=product_id,
                data=data,
                timestamp=datetime.utcnow(),
                raw_data=data
            )
            
            # Call event handlers
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    try:
                        handler(event)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")
            
            # Call stream handlers
            if connection_id in self._stream_handlers:
                for handler in self._stream_handlers[connection_id]:
                    try:
                        handler(event)
                    except Exception as e:
                        logger.error(f"Error in stream handler: {e}")
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")

    def add_event_handler(
        self,
        event_type: str,
        handler: Callable
    ) -> None:
        """
        Add event handler.
        
        Args:
            event_type: Event type
            handler: Handler function
        """
        self._event_handlers[event_type].append(handler)

    def remove_event_handler(
        self,
        event_type: str,
        handler: Callable
    ) -> None:
        """
        Remove event handler.
        
        Args:
            event_type: Event type
            handler: Handler function
        """
        if event_type in self._event_handlers:
            self._event_handlers[event_type].remove(handler)

    def add_stream_handler(
        self,
        connection_id: str,
        handler: Callable
    ) -> None:
        """
        Add stream handler.
        
        Args:
            connection_id: Connection ID
            handler: Handler function
        """
        self._stream_handlers[connection_id].append(handler)

    def remove_stream_handler(
        self,
        connection_id: str,
        handler: Callable
    ) -> None:
        """
        Remove stream handler.
        
        Args:
            connection_id: Connection ID
            handler: Handler function
        """
        if connection_id in self._stream_handlers:
            self._stream_handlers[connection_id].remove(handler)

    # =========================================================================
    # Reconnection
    # =========================================================================

    async def reconnect(self, connection_id: str) -> None:
        """
        Reconnect WebSocket.
        
        Args:
            connection_id: Connection ID
        """
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        
        logger.info(f"Reconnecting: {connection_id}")
        
        # Cancel existing reconnect task
        if connection_id in self._reconnect_tasks:
            self._reconnect_tasks[connection_id].cancel()
        
        # Create reconnect task
        self._reconnect_tasks[connection_id] = asyncio.create_task(
            self._reconnect_loop(connection_id)
        )

    async def _reconnect_loop(self, connection_id: str) -> None:
        """Reconnection loop"""
        attempts = 0
        max_attempts = 5
        delay = 1
        
        while attempts < max_attempts:
            try:
                # Get subscriptions
                subscriptions = self._subscriptions.get(connection_id, [])
                
                # Disconnect old connection
                await self.disconnect(connection_id)
                
                # Reconnect
                is_private = any(s.channel == 'user' for s in subscriptions)
                new_connection_id = await self.connect(is_private=is_private)
                
                # Resubscribe
                if subscriptions:
                    product_ids = list(set(s.product_id for s in subscriptions))
                    channels = list(set(s.channel for s in subscriptions))
                    await self.subscribe(product_ids, channels, connection_id=new_connection_id)
                
                logger.info(f"Reconnected: {connection_id}")
                return
                
            except Exception as e:
                attempts += 1
                logger.warning(f"Reconnect attempt {attempts} failed: {e}")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
        
        logger.error(f"Reconnection failed after {max_attempts} attempts")

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the WebSocket module"""
        # Cancel reconnect tasks
        for task in self._reconnect_tasks.values():
            task.cancel()
        
        await self.disconnect_all()
        
        self._event_handlers.clear()
        self._stream_handlers.clear()
        self._subscriptions.clear()
        
        logger.info("CoinbaseWebSocket closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/coinbase/websocket", tags=["Coinbase WebSocket"])


async def get_websocket(
    api_key: str = Query("", description="Coinbase API Key"),
    api_secret: str = Query("", description="Coinbase API Secret"),
    passphrase: str = Query("", description="Coinbase Passphrase"),
    environment: CoinbaseEnvironment = Query(CoinbaseEnvironment.SANDBOX)
) -> CoinbaseWebSocket:
    """Dependency to get CoinbaseWebSocket instance"""
    return CoinbaseWebSocket(api_key, api_secret, passphrase, environment)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    product_ids: List[str] = Query(...),
    channels: List[str] = Query(...),
    coinbase_ws: CoinbaseWebSocket = Depends(get_websocket)
):
    """WebSocket endpoint for Coinbase streams"""
    await websocket.accept()
    
    try:
        # Connect to Coinbase WebSocket
        connection_id = await coinbase_ws.connect()
        
        # Subscribe to streams
        await coinbase_ws.subscribe(product_ids, channels, connection_id=connection_id)
        
        # Add stream handler to forward messages
        async def forward_message(event):
            await websocket.send_json(event.data)
        
        coinbase_ws.add_stream_handler(connection_id, forward_message)
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await coinbase_ws.close()


@router.websocket("/ws/private")
async def private_websocket_endpoint(
    websocket: WebSocket,
    coinbase_ws: CoinbaseWebSocket = Depends(get_websocket)
):
    """Private WebSocket endpoint for user data streams"""
    await websocket.accept()
    
    try:
        # Connect to private WebSocket
        connection_id = await coinbase_ws.connect(is_private=True)
        
        # Subscribe to private channels
        await coinbase_ws.subscribe(
            product_ids=[],
            channels=["user"],
            is_private=True,
            connection_id=connection_id
        )
        
        # Add stream handler to forward messages
        async def forward_message(event):
            await websocket.send_json(event.data)
        
        coinbase_ws.add_stream_handler(connection_id, forward_message)
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        logger.info("Private WebSocket disconnected")
    except Exception as e:
        logger.error(f"Private WebSocket error: {e}")
    finally:
        await coinbase_ws.close()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CoinbaseWebSocket',
    'CoinbaseStreamType',
    'CoinbaseStreamAction',
    'CoinbaseStreamMessage',
    'CoinbaseStreamSubscription',
    'CoinbaseWebSocketConnection',
    'CoinbaseStreamEvent',
    'router'
]
