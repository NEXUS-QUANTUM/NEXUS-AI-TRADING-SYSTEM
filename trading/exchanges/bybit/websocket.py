"""
NEXUS AI TRADING SYSTEM - Bybit WebSocket Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/websocket.py
Description: Bybit WebSocket streaming with full API integration
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

# Bybit imports
from trading.exchanges.bybit.base import (
    BybitBase,
    BybitEnvironment,
    BybitCategory,
    BybitInterval,
    BybitDepthLevel,
    BybitWebSocketChannel
)
from trading.exchanges.bybit.exceptions import (
    BybitException,
    BybitErrorCode,
    BybitErrorHandler
)
from trading.exchanges.bybit.converter import BybitConverter

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BybitStreamType(str, Enum):
    """Bybit stream types"""
    ORDER_BOOK = "orderbook"
    TRADE = "trade"
    KLINE = "kline"
    TICKER = "ticker"
    BOOK_TICKER = "bookticker"
    POSITION = "position"
    ORDER = "order"
    EXECUTION = "execution"
    WALLET = "wallet"


class BybitStreamAction(str, Enum):
    """Bybit stream actions"""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    PONG = "pong"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BybitStreamMessage(BaseModel):
    """Bybit stream message"""
    topic: str
    data: Dict[str, Any]
    timestamp: datetime


class BybitStreamSubscription(BaseModel):
    """Bybit stream subscription"""
    stream_name: str
    symbol: str
    channel: str
    params: Optional[Dict[str, Any]] = None
    callback: Optional[Callable] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BybitWebSocketConnection:
    """Bybit WebSocket connection"""
    connection_id: str
    url: str
    websocket: websockets.WebSocketClientProtocol
    subscriptions: List[str]
    connected_at: datetime
    last_heartbeat: datetime
    active: bool


@dataclass
class BybitStreamEvent:
    """Bybit stream event"""
    event_type: str
    symbol: str
    data: Dict[str, Any]
    timestamp: datetime
    raw_data: Dict[str, Any]


# =============================================================================
# BYBIT WEBSOCKET
# =============================================================================

class BybitWebSocket:
    """
    Bybit WebSocket Streaming with full API integration.
    
    Features:
    - Multiple stream types (orderbook, trade, kline, ticker, position, order, execution, wallet)
    - Automatic reconnection
    - Heartbeat management
    - Subscription management
    - Event handling
    - Multiple connection support
    - Data conversion
    - Error handling
    - Public and private streams
    """

    PRODUCTION_PUBLIC_WS_URL = "wss://stream.bybit.com/v5/public/linear"
    TESTNET_PUBLIC_WS_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
    
    PRODUCTION_PRIVATE_WS_URL = "wss://stream.bybit.com/v5/private"
    TESTNET_PRIVATE_WS_URL = "wss://stream-testnet.bybit.com/v5/private"
    
    PRODUCTION_SPOT_WS_URL = "wss://stream.bybit.com/v5/public/spot"
    TESTNET_SPOT_WS_URL = "wss://stream-testnet.bybit.com/v5/public/spot"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        environment: BybitEnvironment = BybitEnvironment.TESTNET,
        category: BybitCategory = BybitCategory.LINEAR,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BybitWebSocket.
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            environment: Bybit environment
            category: Bybit category
            config: Exchange configuration
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.environment = environment
        self.category = category
        self.config = config or ExchangeConfig()
        
        # WebSocket URLs
        self.public_ws_url = self._get_public_ws_url()
        self.private_ws_url = self._get_private_ws_url()
        
        # Connections
        self._connections: Dict[str, BybitWebSocketConnection] = {}
        self._connection_counter: int = 0
        
        # Subscriptions
        self._subscriptions: Dict[str, List[BybitStreamSubscription]] = defaultdict(list)
        self._subscription_counters: Dict[str, int] = defaultdict(int)
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._stream_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Converter
        self.converter = BybitConverter()
        
        # Error handler
        self._error_handler = BybitErrorHandler()
        
        # State
        self._is_running: bool = False
        self._reconnect_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info(f"BybitWebSocket initialized in {environment.value}")

    def _get_public_ws_url(self) -> str:
        """Get public WebSocket URL based on environment and category"""
        if self.environment == BybitEnvironment.TESTNET:
            if self.category == BybitCategory.SPOT:
                return self.TESTNET_SPOT_WS_URL
            return self.TESTNET_PUBLIC_WS_URL
        
        if self.category == BybitCategory.SPOT:
            return self.PRODUCTION_SPOT_WS_URL
        return self.PRODUCTION_PUBLIC_WS_URL

    def _get_private_ws_url(self) -> str:
        """Get private WebSocket URL based on environment"""
        if self.environment == BybitEnvironment.TESTNET:
            return self.TESTNET_PRIVATE_WS_URL
        return self.PRODUCTION_PRIVATE_WS_URL

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect_public(
        self,
        stream_key: Optional[str] = None
    ) -> str:
        """
        Connect to public WebSocket.
        
        Args:
            stream_key: Stream key
            
        Returns:
            str: Connection ID
        """
        return await self._connect(self.public_ws_url, stream_key)

    async def connect_private(self) -> str:
        """
        Connect to private WebSocket.
        
        Returns:
            str: Connection ID
        """
        return await self._connect(self.private_ws_url, is_private=True)

    async def _connect(
        self,
        url: str,
        stream_key: Optional[str] = None,
        is_private: bool = False
    ) -> str:
        """
        Connect to WebSocket.
        
        Args:
            url: WebSocket URL
            stream_key: Stream key
            is_private: Whether this is a private connection
            
        Returns:
            str: Connection ID
        """
        try:
            # Build URL
            if stream_key:
                url = f"{url}/{stream_key}"
            
            # Connect
            ws = await websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            # Create connection
            self._connection_counter += 1
            connection_id = f"ws_{self._connection_counter}_{int(time.time())}"
            
            connection = BybitWebSocketConnection(
                connection_id=connection_id,
                url=url,
                websocket=ws,
                subscriptions=[],
                connected_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow(),
                active=True
            )
            
            self._connections[connection_id] = connection
            
            # Authenticate if private
            if is_private:
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
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret required for private connection")
        
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        
        # Generate authentication payload
        timestamp = str(int(time.time() * 1000))
        expires = str(int(time.time() * 1000) + 10000)
        
        # Generate signature
        signature_payload = timestamp + self.api_key + expires
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Send authentication request
        auth_msg = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
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
            
            # Check for ping
            if data.get('op') == 'ping':
                await self._send_pong(connection_id)
                return
            
            # Check for authentication response
            if data.get('op') == 'auth':
                if data.get('success'):
                    logger.info(f"Authentication successful: {connection_id}")
                else:
                    logger.error(f"Authentication failed: {data.get('ret_msg')}")
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
        pong_msg = {"op": "pong"}
        await connection.websocket.send(json.dumps(pong_msg))

    # =========================================================================
    # Subscription Management
    # =========================================================================

    async def subscribe(
        self,
        symbol: str,
        channels: List[str],
        params: Optional[Dict[str, Any]] = None,
        connection_id: Optional[str] = None,
        is_private: bool = False
    ) -> str:
        """
        Subscribe to streams.
        
        Args:
            symbol: Symbol
            channels: List of channels
            params: Additional parameters
            connection_id: Connection ID
            is_private: Whether this is a private subscription
            
        Returns:
            str: Connection ID
        """
        try:
            # Build subscription args
            args = []
            for channel in channels:
                if channel == 'orderbook':
                    depth = params.get('depth_level', '10') if params else '10'
                    args.append(f"{channel}.{depth}.{symbol}")
                elif channel == 'kline':
                    interval = params.get('interval', '1') if params else '1'
                    args.append(f"{channel}.{interval}.{symbol}")
                else:
                    args.append(f"{channel}.{symbol}")
            
            # Determine URL
            if is_private:
                url = self.private_ws_url
            else:
                url = self.public_ws_url
            
            # Connect if no connection
            if not connection_id:
                if is_private:
                    connection_id = await self.connect_private()
                else:
                    connection_id = await self.connect_public()
            
            # Send subscription
            await self._send_subscribe(connection_id, args)
            
            # Store subscriptions
            for arg in args:
                subscription = BybitStreamSubscription(
                    stream_name=arg,
                    symbol=symbol,
                    channel=channel,
                    params=params
                )
                self._subscriptions[connection_id].append(subscription)
                self._subscription_counters[arg] += 1
            
            logger.info(f"Subscribed to {len(args)} streams for {symbol}")
            return connection_id
            
        except Exception as e:
            logger.error(f"Error subscribing: {e}")
            raise

    async def unsubscribe(
        self,
        symbol: str,
        channels: List[str],
        connection_id: str
    ) -> None:
        """
        Unsubscribe from streams.
        
        Args:
            symbol: Symbol
            channels: List of channels
            connection_id: Connection ID
        """
        try:
            # Build unsubscribe args
            args = []
            for channel in channels:
                if channel == 'orderbook':
                    args.append(f"{channel}.*.{symbol}")
                elif channel == 'kline':
                    args.append(f"{channel}.*.{symbol}")
                else:
                    args.append(f"{channel}.{symbol}")
            
            # Send unsubscription
            await self._send_unsubscribe(connection_id, args)
            
            # Remove subscriptions
            if connection_id in self._subscriptions:
                self._subscriptions[connection_id] = [
                    s for s in self._subscriptions[connection_id]
                    if s.symbol != symbol or s.channel not in channels
                ]
            
            logger.info(f"Unsubscribed from {len(args)} streams for {symbol}")
            
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
            raise

    async def _send_subscribe(
        self,
        connection_id: str,
        args: List[str]
    ) -> None:
        """Send subscription request"""
        if connection_id not in self._connections:
            raise ValueError(f"Connection {connection_id} not found")
        
        connection = self._connections[connection_id]
        
        message = {
            "op": "subscribe",
            "args": args,
            "id": self._get_next_request_id()
        }
        
        await connection.websocket.send(json.dumps(message))
        logger.debug(f"Sent subscription: {args}")

    async def _send_unsubscribe(
        self,
        connection_id: str,
        args: List[str]
    ) -> None:
        """Send unsubscription request"""
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        
        message = {
            "op": "unsubscribe",
            "args": args,
            "id": self._get_next_request_id()
        }
        
        await connection.websocket.send(json.dumps(message))
        logger.debug(f"Sent unsubscription: {args}")

    def _get_next_request_id(self) -> int:
        """Get next request ID"""
        return int(time.time() * 1000) % 1000000

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
            # Determine event type and symbol
            topic = data.get('topic', '')
            if 'orderbook' in topic:
                event_type = 'orderbook'
                symbol = topic.split('.')[-1]
            elif 'trade' in topic:
                event_type = 'trade'
                symbol = topic.split('.')[-1]
            elif 'kline' in topic:
                event_type = 'kline'
                symbol = topic.split('.')[-1]
            elif 'ticker' in topic:
                event_type = 'ticker'
                symbol = topic.split('.')[-1]
            elif 'position' in topic:
                event_type = 'position'
                symbol = data.get('data', {}).get('symbol', '')
            elif 'order' in topic:
                event_type = 'order'
                symbol = data.get('data', {}).get('symbol', '')
            elif 'execution' in topic:
                event_type = 'execution'
                symbol = data.get('data', {}).get('symbol', '')
            else:
                event_type = 'unknown'
                symbol = ''
            
            # Create event
            event = BybitStreamEvent(
                event_type=event_type,
                symbol=symbol,
                data=data.get('data', {}),
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
                new_connection_id = await self.connect_public()
                
                # Resubscribe
                if subscriptions:
                    args = [s.stream_name for s in subscriptions]
                    await self._send_subscribe(new_connection_id, args)
                
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
        
        logger.info("BybitWebSocket closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/bybit/websocket", tags=["Bybit WebSocket"])


async def get_websocket(
    api_key: str = Query("", description="Bybit API Key"),
    api_secret: str = Query("", description="Bybit API Secret"),
    environment: BybitEnvironment = Query(BybitEnvironment.TESTNET),
    category: BybitCategory = Query(BybitCategory.LINEAR)
) -> BybitWebSocket:
    """Dependency to get BybitWebSocket instance"""
    return BybitWebSocket(api_key, api_secret, environment, category)


@router.websocket("/ws/{symbol}")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str,
    channels: List[str] = Query(...),
    depth: str = Query("10"),
    interval: str = Query("1"),
    category: BybitCategory = Query(BybitCategory.LINEAR),
    bybit_ws: BybitWebSocket = Depends(get_websocket)
):
    """WebSocket endpoint for Bybit streams"""
    await websocket.accept()
    
    try:
        # Connect to Bybit WebSocket
        connection_id = await bybit_ws.connect_public()
        
        # Subscribe to streams
        params = {'depth_level': depth, 'interval': interval}
        await bybit_ws.subscribe(symbol, channels, params, connection_id)
        
        # Add stream handler to forward messages
        async def forward_message(event):
            await websocket.send_json(event.data)
        
        bybit_ws.add_stream_handler(connection_id, forward_message)
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {symbol}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await bybit_ws.close()


@router.websocket("/ws/private")
async def private_websocket_endpoint(
    websocket: WebSocket,
    bybit_ws: BybitWebSocket = Depends(get_websocket)
):
    """Private WebSocket endpoint for user data streams"""
    await websocket.accept()
    
    try:
        # Connect to private WebSocket
        connection_id = await bybit_ws.connect_private()
        
        # Subscribe to private channels
        await bybit_ws.subscribe(
            symbol="",
            channels=["position", "order", "execution", "wallet"],
            is_private=True,
            connection_id=connection_id
        )
        
        # Add stream handler to forward messages
        async def forward_message(event):
            await websocket.send_json(event.data)
        
        bybit_ws.add_stream_handler(connection_id, forward_message)
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        logger.info("Private WebSocket disconnected")
    except Exception as e:
        logger.error(f"Private WebSocket error: {e}")
    finally:
        await bybit_ws.close()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitWebSocket',
    'BybitStreamType',
    'BybitStreamAction',
    'BybitStreamMessage',
    'BybitStreamSubscription',
    'BybitWebSocketConnection',
    'BybitStreamEvent',
    'router'
]
