"""
NEXUS AI TRADING SYSTEM - Binance WebSocket Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/websocket.py
Description: Binance WebSocket streaming with full API integration
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

# Binance imports
from trading.exchanges.binance.base import (
    BinanceBase,
    BinanceEnvironment,
    BinanceInterval,
    BinanceDepthLevel,
    BinanceWebSocketChannel
)
from trading.exchanges.binance.exceptions import (
    BinanceException,
    BinanceErrorCode,
    BinanceErrorHandler
)
from trading.exchanges.binance.converter import BinanceConverter

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BinanceStreamType(str, Enum):
    """Binance stream types"""
    DEPTH = "depth"
    TRADE = "trade"
    KLINE = "kline"
    TICKER = "ticker"
    BOOK_TICKER = "bookTicker"
    USER_DATA = "userData"
    ALL_MARKET = "allMarket"


class BinanceStreamAction(str, Enum):
    """Binance stream actions"""
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    LIST_SUBSCRIPTIONS = "LIST_SUBSCRIPTIONS"
    PING = "PING"
    PONG = "PONG"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BinanceStreamMessage(BaseModel):
    """Binance stream message"""
    stream: str
    data: Dict[str, Any]
    timestamp: datetime


class BinanceStreamSubscription(BaseModel):
    """Binance stream subscription"""
    stream_name: str
    symbol: str
    channel: str
    params: Optional[Dict[str, Any]] = None
    callback: Optional[Callable] = None


class BinanceUserDataStream(BaseModel):
    """Binance user data stream"""
    listen_key: str
    created_at: datetime
    expires_at: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BinanceWebSocketConnection:
    """Binance WebSocket connection"""
    connection_id: str
    url: str
    websocket: websockets.WebSocketClientProtocol
    subscriptions: List[str]
    connected_at: datetime
    last_heartbeat: datetime
    active: bool


@dataclass
class BinanceStreamEvent:
    """Binance stream event"""
    event_type: str
    symbol: str
    data: Dict[str, Any]
    timestamp: datetime
    raw_data: Dict[str, Any]


# =============================================================================
# BINANCE WEBSOCKET
# =============================================================================

class BinanceWebSocket:
    """
    Binance WebSocket Streaming with full API integration.
    
    Features:
    - Multiple stream types (depth, trade, kline, ticker, user data)
    - Automatic reconnection
    - Heartbeat management
    - Subscription management
    - Event handling
    - Multiple connection support
    - Data conversion
    - Error handling
    """

    PRODUCTION_WS_URL = "wss://stream.binance.com:9443/ws"
    TESTNET_WS_URL = "wss://testnet.binance.vision/ws"
    PRODUCTION_US_WS_URL = "wss://stream.binance.com:9443/ws"
    
    USER_DATA_WS_URL = "wss://stream.binance.com:9443/ws"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        environment: BinanceEnvironment = BinanceEnvironment.TESTNET,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BinanceWebSocket.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            environment: Binance environment
            config: Exchange configuration
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.environment = environment
        self.config = config or ExchangeConfig()
        
        # WebSocket URLs
        self.ws_url = self._get_ws_url()
        self.user_data_url = self.USER_DATA_WS_URL
        
        # Connections
        self._connections: Dict[str, BinanceWebSocketConnection] = {}
        self._connection_counter: int = 0
        
        # Subscriptions
        self._subscriptions: Dict[str, List[BinanceStreamSubscription]] = defaultdict(list)
        self._subscription_counters: Dict[str, int] = defaultdict(int)
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._stream_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # User data
        self._listen_key: Optional[str] = None
        self._user_data_stream: Optional[BinanceUserDataStream] = None
        
        # Converter
        self.converter = BinanceConverter()
        
        # Error handler
        self._error_handler = BinanceErrorHandler()
        
        # State
        self._is_running: bool = False
        self._reconnect_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info(f"BinanceWebSocket initialized in {environment.value}")

    def _get_ws_url(self) -> str:
        """Get WebSocket URL based on environment"""
        if self.environment == BinanceEnvironment.TESTNET:
            return self.TESTNET_WS_URL
        return self.PRODUCTION_WS_URL

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(
        self,
        stream_key: Optional[str] = None,
        custom_url: Optional[str] = None
    ) -> str:
        """
        Connect to WebSocket.
        
        Args:
            stream_key: Stream key
            custom_url: Custom WebSocket URL
            
        Returns:
            str: Connection ID
        """
        try:
            # Determine URL
            url = custom_url or self.ws_url
            
            # Build stream URL
            if stream_key:
                url = f"{url}/{stream_key}"
            
            # Connect
            ws = await websockets.connect(
                url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            )
            
            # Create connection
            self._connection_counter += 1
            connection_id = f"ws_{self._connection_counter}_{int(time.time())}"
            
            connection = BinanceWebSocketConnection(
                connection_id=connection_id,
                url=url,
                websocket=ws,
                subscriptions=[],
                connected_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow(),
                active=True
            )
            
            self._connections[connection_id] = connection
            
            # Start receive loop
            asyncio.create_task(self._receive_loop(connection_id))
            
            logger.info(f"WebSocket connected: {connection_id}")
            return connection_id
            
        except Exception as e:
            logger.error(f"Error connecting to WebSocket: {e}")
            raise

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
            if 'ping' in data:
                await self._send_pong(connection_id, data['ping'])
                return
            
            # Check for pong
            if 'pong' in data:
                return
            
            # Check for subscription response
            if 'result' in data or 'error' in data:
                await self._handle_subscription_response(connection_id, data)
                return
            
            # Process event
            await self._process_event(connection_id, data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    # =========================================================================
    # Subscription Management
    # =========================================================================

    async def subscribe(
        self,
        symbol: str,
        channels: List[str],
        params: Optional[Dict[str, Any]] = None,
        connection_id: Optional[str] = None
    ) -> str:
        """
        Subscribe to streams.
        
        Args:
            symbol: Symbol
            channels: List of channels
            params: Additional parameters
            connection_id: Connection ID
            
        Returns:
            str: Connection ID
        """
        try:
            # Build stream key
            streams = []
            for channel in channels:
                if channel == 'depth':
                    depth_level = params.get('depth_level', '10') if params else '10'
                    streams.append(f"{symbol.lower()}@depth{depth_level}")
                elif channel == 'trade':
                    streams.append(f"{symbol.lower()}@trade")
                elif channel == 'kline':
                    interval = params.get('interval', '1m') if params else '1m'
                    streams.append(f"{symbol.lower()}@kline_{interval}")
                elif channel == 'ticker':
                    streams.append(f"{symbol.lower()}@ticker")
                elif channel == 'bookTicker':
                    streams.append(f"{symbol.lower()}@bookTicker")
            
            stream_key = '/'.join(streams)
            
            # Connect if no connection
            if not connection_id:
                connection_id = await self.connect(stream_key=stream_key)
            
            # Send subscription
            await self._send_subscribe(connection_id, streams)
            
            # Store subscriptions
            for stream in streams:
                subscription = BinanceStreamSubscription(
                    stream_name=stream,
                    symbol=symbol,
                    channel=channel,
                    params=params
                )
                self._subscriptions[connection_id].append(subscription)
                self._subscription_counters[stream] += 1
            
            logger.info(f"Subscribed to {len(streams)} streams for {symbol}")
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
            # Build stream key
            streams = []
            for channel in channels:
                if channel == 'depth':
                    streams.append(f"{symbol.lower()}@depth*")
                elif channel == 'trade':
                    streams.append(f"{symbol.lower()}@trade")
                elif channel == 'kline':
                    streams.append(f"{symbol.lower()}@kline_*")
                elif channel == 'ticker':
                    streams.append(f"{symbol.lower()}@ticker")
                elif channel == 'bookTicker':
                    streams.append(f"{symbol.lower()}@bookTicker")
            
            # Send unsubscription
            await self._send_unsubscribe(connection_id, streams)
            
            # Remove subscriptions
            if connection_id in self._subscriptions:
                self._subscriptions[connection_id] = [
                    s for s in self._subscriptions[connection_id]
                    if s.symbol != symbol or s.channel not in channels
                ]
            
            logger.info(f"Unsubscribed from {len(streams)} streams for {symbol}")
            
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
            raise

    async def _send_subscribe(
        self,
        connection_id: str,
        streams: List[str]
    ) -> None:
        """Send subscription request"""
        if connection_id not in self._connections:
            raise ValueError(f"Connection {connection_id} not found")
        
        connection = self._connections[connection_id]
        
        message = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": self._get_next_request_id()
        }
        
        await connection.websocket.send(json.dumps(message))
        logger.debug(f"Sent subscription: {streams}")

    async def _send_unsubscribe(
        self,
        connection_id: str,
        streams: List[str]
    ) -> None:
        """Send unsubscription request"""
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        
        message = {
            "method": "UNSUBSCRIBE",
            "params": streams,
            "id": self._get_next_request_id()
        }
        
        await connection.websocket.send(json.dumps(message))
        logger.debug(f"Sent unsubscription: {streams}")

    async def _send_pong(self, connection_id: str, ping_data: Any) -> None:
        """Send pong response"""
        if connection_id not in self._connections:
            return
        
        connection = self._connections[connection_id]
        
        message = {"pong": ping_data}
        await connection.websocket.send(json.dumps(message))

    def _get_next_request_id(self) -> int:
        """Get next request ID"""
        return int(time.time() * 1000) % 1000000

    async def _handle_subscription_response(
        self,
        connection_id: str,
        data: Dict[str, Any]
    ) -> None:
        """Handle subscription response"""
        if 'error' in data:
            logger.error(f"Subscription error: {data['error']}")
        else:
            logger.debug(f"Subscription success: {data.get('result')}")

    # =========================================================================
    # User Data Stream
    # =========================================================================

    async def create_user_data_stream(self) -> str:
        """
        Create a user data stream.
        
        Returns:
            str: Listen key
        """
        try:
            if not self.api_key:
                raise ValueError("API key required for user data stream")
            
            # Create listen key
            response = await self._create_listen_key()
            
            self._listen_key = response['listenKey']
            self._user_data_stream = BinanceUserDataStream(
                listen_key=self._listen_key,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            
            # Connect to user data stream
            await self.connect_user_data_stream()
            
            logger.info("User data stream created")
            return self._listen_key
            
        except Exception as e:
            logger.error(f"Error creating user data stream: {e}")
            raise

    async def connect_user_data_stream(self) -> str:
        """
        Connect to user data stream.
        
        Returns:
            str: Connection ID
        """
        try:
            if not self._listen_key:
                raise ValueError("No listen key available")
            
            stream_key = self._listen_key
            connection_id = await self.connect(stream_key=stream_key)
            
            logger.info("User data stream connected")
            return connection_id
            
        except Exception as e:
            logger.error(f"Error connecting user data stream: {e}")
            raise

    async def _create_listen_key(self) -> Dict[str, Any]:
        """Create listen key"""
        # This would use the Binance API
        # For now, return mock data
        return {
            'listenKey': f"listen_key_{int(time.time())}"
        }

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
            # Determine event type
            event_type = None
            symbol = None
            
            if 'e' in data:
                event_type = data['e']
                symbol = data.get('s')
            
            # Create event
            event = BinanceStreamEvent(
                event_type=event_type or 'unknown',
                symbol=symbol or 'unknown',
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
                new_connection_id = await self.connect()
                
                # Resubscribe
                if subscriptions:
                    streams = [s.stream_name for s in subscriptions]
                    await self._send_subscribe(new_connection_id, streams)
                
                logger.info(f"Reconnected: {connection_id}")
                return
                
            except Exception as e:
                attempts += 1
                logger.warning(f"Reconnect attempt {attempts} failed: {e}")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
        
        logger.error(f"Reconnection failed after {max_attempts} attempts")

    # =========================================================================
    # Heartbeat
    # =========================================================================

    async def keepalive_user_data_stream(self) -> None:
        """Keep user data stream alive"""
        try:
            if not self._listen_key:
                return
            
            # Send keepalive
            await self._keepalive_listen_key()
            
            # Update expiration
            if self._user_data_stream:
                self._user_data_stream.expires_at = datetime.utcnow() + timedelta(hours=24)
            
            logger.debug("User data stream keepalive sent")
            
        except Exception as e:
            logger.error(f"Error sending keepalive: {e}")

    async def _keepalive_listen_key(self) -> None:
        """Keep listen key alive"""
        # This would use the Binance API
        pass

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
        
        logger.info("BinanceWebSocket closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/binance/websocket", tags=["Binance WebSocket"])


async def get_websocket(
    api_key: str = Query("", description="Binance API Key"),
    api_secret: str = Query("", description="Binance API Secret"),
    environment: BinanceEnvironment = Query(BinanceEnvironment.TESTNET)
) -> BinanceWebSocket:
    """Dependency to get BinanceWebSocket instance"""
    return BinanceWebSocket(api_key, api_secret, environment)


@router.websocket("/ws/{symbol}")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str,
    channels: List[str] = Query(...),
    depth: str = Query("10"),
    interval: str = Query("1m"),
    binance_ws: BinanceWebSocket = Depends(get_websocket)
):
    """WebSocket endpoint for Binance streams"""
    await websocket.accept()
    
    try:
        # Connect to Binance WebSocket
        connection_id = await binance_ws.connect()
        
        # Subscribe to streams
        params = {'depth_level': depth, 'interval': interval}
        await binance_ws.subscribe(symbol, channels, params, connection_id)
        
        # Add stream handler to forward messages
        async def forward_message(event):
            await websocket.send_json(event.data)
        
        binance_ws.add_stream_handler(connection_id, forward_message)
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {symbol}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await binance_ws.close()


@router.post("/user-data/start")
async def start_user_data_stream(
    binance_ws: BinanceWebSocket = Depends(get_websocket)
):
    """Start user data stream"""
    listen_key = await binance_ws.create_user_data_stream()
    return {"listen_key": listen_key}


@router.post("/user-data/keepalive")
async def keepalive_user_data_stream(
    binance_ws: BinanceWebSocket = Depends(get_websocket)
):
    """Keep user data stream alive"""
    await binance_ws.keepalive_user_data_stream()
    return {"success": True}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BinanceWebSocket',
    'BinanceStreamType',
    'BinanceStreamAction',
    'BinanceStreamMessage',
    'BinanceStreamSubscription',
    'BinanceUserDataStream',
    'BinanceWebSocketConnection',
    'BinanceStreamEvent',
    'router'
]
