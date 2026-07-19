"""
NEXUS AI TRADING SYSTEM - Coinbase Base Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/coinbase/base.py
Description: Coinbase exchange base classes and utilities with full API integration
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from urllib.parse import urlencode

import aiohttp
import websockets
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status, WebSocket, WebSocketDisconnect

# NEXUS Internal Imports
from shared.configs.exchange_config import ExchangeConfig
from shared.constants.trading_constants import ORDER_TYPES, POSITION_DIRECTIONS, TIME_FRAMES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class CoinbaseEnvironment(str, Enum):
    """Coinbase environment"""
    PRODUCTION = "production"
    SANDBOX = "sandbox"


class CoinbaseProductType(str, Enum):
    """Coinbase product types"""
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"


class CoinbaseGranularity(str, Enum):
    """Coinbase candle granularities"""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    ONE_WEEK = "7d"
    ONE_MONTH = "1M"


class CoinbaseWebSocketChannel(str, Enum):
    """Coinbase WebSocket channels"""
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    TICKER = "ticker"
    LEVEL2 = "level2"
    USER = "user"
    MATCHES = "matches"
    FULL = "full"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CoinbaseCandle(BaseModel):
    """Coinbase candle data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class CoinbaseTicker(BaseModel):
    """Coinbase ticker data"""
    product_id: str
    price: float
    price_change: float
    price_change_pct: float
    volume: float
    high: float
    low: float
    open: float
    close: float
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    timestamp: datetime


class CoinbaseOrderBookLevel(BaseModel):
    """Coinbase order book level"""
    price: float
    size: float
    order_count: int


class CoinbaseOrderBook(BaseModel):
    """Coinbase order book"""
    product_id: str
    bids: List[CoinbaseOrderBookLevel]
    asks: List[CoinbaseOrderBookLevel]
    timestamp: datetime
    sequence: int


class CoinbaseTrade(BaseModel):
    """Coinbase trade data"""
    product_id: str
    price: float
    size: float
    side: str
    trade_time: datetime
    trade_id: int


class CoinbaseProductInfo(BaseModel):
    """Coinbase product information"""
    product_id: str
    base_currency: str
    quote_currency: str
    base_min_size: float
    base_max_size: float
    quote_increment: float
    base_increment: float
    display_name: str
    status: str
    trading_disabled: bool


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CoinbaseApiLimits:
    """Coinbase API limits"""
    requests_per_second: int = 10
    orders_per_second: int = 5
    websocket_connections: int = 5


@dataclass
class CoinbaseWebSocketMessage:
    """Coinbase WebSocket message"""
    channel: str
    data: Dict[str, Any]
    timestamp: datetime


@dataclass
class CoinbaseStreamConfig:
    """Coinbase stream configuration"""
    product_ids: List[str]
    channels: List[str]
    granularity: Optional[str] = None


# =============================================================================
# COINBASE BASE CLASS
# =============================================================================

class CoinbaseBase:
    """
    Coinbase Exchange Base Class with full API integration.
    
    Provides:
    - API request handling
    - Authentication
    - Rate limiting
    - WebSocket management
    - Market data
    - Order book management
    - Stream handling
    - Error handling
    """

    PRODUCTION_BASE_URL = "https://api.coinbase.com"
    SANDBOX_BASE_URL = "https://api-public.sandbox.exchange.coinbase.com"
    
    PRODUCTION_WS_URL = "wss://ws-feed.exchange.coinbase.com"
    SANDBOX_WS_URL = "wss://ws-feed-public.sandbox.exchange.coinbase.com"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        environment: CoinbaseEnvironment = CoinbaseEnvironment.SANDBOX,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize CoinbaseBase.
        
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
        
        # Base URLs
        self.base_url = self._get_base_url()
        self.ws_url = self._get_ws_url()
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        
        # Rate limiting
        self._rate_limits = CoinbaseApiLimits()
        self._request_timestamps: List[float] = []
        self._order_timestamps: List[float] = []
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Product info
        self._product_info: Dict[str, CoinbaseProductInfo] = {}
        
        # Cache
        self._ticker_cache: Dict[str, CoinbaseTicker] = {}
        self._order_book_cache: Dict[str, CoinbaseOrderBook] = {}
        
        # Stream handlers
        self._stream_handlers: Dict[str, List] = {}
        
        # WebSocket manager
        self._ws_manager = WebSocketManager()
        
        logger.info(f"CoinbaseBase initialized in {environment.value}")

    def _get_base_url(self) -> str:
        """Get base URL based on environment"""
        if self.environment == CoinbaseEnvironment.SANDBOX:
            return self.SANDBOX_BASE_URL
        return self.PRODUCTION_BASE_URL

    def _get_ws_url(self) -> str:
        """Get WebSocket URL based on environment"""
        if self.environment == CoinbaseEnvironment.SANDBOX:
            return self.SANDBOX_WS_URL
        return self.PRODUCTION_WS_URL

    # =========================================================================
    # Session Management
    # =========================================================================

    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession(
            headers={'Content-Type': 'application/json'},
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
            self._session = None
        
        await self.close_websockets()

    # =========================================================================
    # API Request Methods
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5, backoff=2.0)
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """
        Make an API request to Coinbase.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request data
            signed: Whether request requires signing
            
        Returns:
            Dict[str, Any]: Response data
        """
        try:
            # Check rate limits
            await self._check_rate_limits()
            
            # Prepare request
            url = f"{self.base_url}{endpoint}"
            headers = {'Content-Type': 'application/json'}
            
            # Add authentication if required
            if signed:
                timestamp = str(int(time.time()))
                method_str = method
                path = endpoint
                
                # Build message
                if method == 'GET':
                    if params:
                        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                        path = f"{endpoint}?{query_string}"
                    message = f"{timestamp}{method_str}{path}"
                else:
                    if data:
                        body = json.dumps(data, separators=(',', ':'))
                        message = f"{timestamp}{method_str}{path}{body}"
                    else:
                        message = f"{timestamp}{method_str}{path}"
                
                # Generate signature
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    message.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                headers['CB-ACCESS-KEY'] = self.api_key
                headers['CB-ACCESS-SIGN'] = signature
                headers['CB-ACCESS-TIMESTAMP'] = timestamp
                headers['CB-ACCESS-PASSPHRASE'] = self.passphrase
            
            # Make request
            async with self._session.request(
                method=method,
                url=url,
                params=params if method == 'GET' else None,
                json=data if method == 'POST' else None,
                headers=headers
            ) as response:
                # Update rate limits
                self._update_rate_limits()
                
                # Parse response
                response_data = await response.json()
                
                if response.status >= 400:
                    error_msg = response_data.get('message', 'Unknown error')
                    raise Exception(f"Coinbase API error: {error_msg}")
                
                return response_data
                
        except asyncio.TimeoutError:
            raise Exception("Request timeout")
        except Exception as e:
            logger.error(f"API request error: {e}")
            raise

    async def _check_rate_limits(self) -> None:
        """Check if rate limits are exceeded"""
        now = time.time()
        
        # Check requests per second
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 1]
        if len(self._request_timestamps) >= self._rate_limits.requests_per_second:
            sleep_time = 1 - (now - self._request_timestamps[0]) + 0.1
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                await self._check_rate_limits()

    def _update_rate_limits(self) -> None:
        """Update rate limit tracking"""
        self._request_timestamps.append(time.time())

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature"""
        timestamp = str(int(time.time()))
        message = f"{timestamp}GET{urlencode(params)}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_ticker(self, product_id: str) -> CoinbaseTicker:
        """
        Get ticker for product.
        
        Args:
            product_id: Product ID
            
        Returns:
            CoinbaseTicker: Ticker data
        """
        try:
            # Check cache
            if product_id in self._ticker_cache:
                cached = self._ticker_cache[product_id]
                if (datetime.utcnow() - cached.timestamp).seconds < 5:
                    return cached
            
            response = await self._request(
                method='GET',
                endpoint=f'/api/v3/brokerage/products/{product_id}/ticker',
                signed=True
            )
            
            data = response
            
            ticker = CoinbaseTicker(
                product_id=product_id,
                price=float(data.get('price', 0)),
                price_change=0,
                price_change_pct=0,
                volume=0,
                high=0,
                low=0,
                open=0,
                close=0,
                bid=float(data.get('bid', 0)),
                ask=float(data.get('ask', 0)),
                bid_size=float(data.get('bid_size', 0)),
                ask_size=float(data.get('ask_size', 0)),
                timestamp=datetime.utcnow()
            )
            
            # Cache
            self._ticker_cache[product_id] = ticker
            
            return ticker
            
        except Exception as e:
            logger.error(f"Error getting ticker for {product_id}: {e}")
            raise

    async def get_candles(
        self,
        product_id: str,
        granularity: CoinbaseGranularity = CoinbaseGranularity.ONE_HOUR,
        limit: int = 500
    ) -> List[CoinbaseCandle]:
        """
        Get candle data.
        
        Args:
            product_id: Product ID
            granularity: Candle granularity
            limit: Number of candles
            
        Returns:
            List[CoinbaseCandle]: Candle data
        """
        try:
            params = {
                'granularity': granularity.value,
                'limit': limit
            }
            
            response = await self._request(
                method='GET',
                endpoint=f'/api/v3/brokerage/products/{product_id}/candles',
                params=params,
                signed=True
            )
            
            candles = []
            for data in response.get('candles', []):
                candles.append(CoinbaseCandle(
                    timestamp=datetime.fromtimestamp(data[0]),
                    open=float(data[1]),
                    high=float(data[2]),
                    low=float(data[3]),
                    close=float(data[4]),
                    volume=float(data[5])
                ))
            
            return candles
            
        except Exception as e:
            logger.error(f"Error getting candles for {product_id}: {e}")
            raise

    async def get_order_book(
        self,
        product_id: str,
        level: int = 2
    ) -> CoinbaseOrderBook:
        """
        Get order book.
        
        Args:
            product_id: Product ID
            level: Order book level (1, 2, 3)
            
        Returns:
            CoinbaseOrderBook: Order book data
        """
        try:
            # Check cache
            if product_id in self._order_book_cache:
                cached = self._order_book_cache[product_id]
                if (datetime.utcnow() - cached.timestamp).seconds < 5:
                    return cached
            
            response = await self._request(
                method='GET',
                endpoint=f'/api/v3/brokerage/products/{product_id}/book',
                params={'level': level},
                signed=True
            )
            
            data = response
            
            bids = []
            for b in data.get('bids', [])[:20]:
                bids.append(CoinbaseOrderBookLevel(
                    price=float(b[0]),
                    size=float(b[1]),
                    order_count=int(b[2]) if len(b) > 2 else 0
                ))
            
            asks = []
            for a in data.get('asks', [])[:20]:
                asks.append(CoinbaseOrderBookLevel(
                    price=float(a[0]),
                    size=float(a[1]),
                    order_count=int(a[2]) if len(a) > 2 else 0
                ))
            
            order_book = CoinbaseOrderBook(
                product_id=product_id,
                bids=bids,
                asks=asks,
                timestamp=datetime.utcnow(),
                sequence=data.get('sequence', 0)
            )
            
            # Cache
            self._order_book_cache[product_id] = order_book
            
            return order_book
            
        except Exception as e:
            logger.error(f"Error getting order book for {product_id}: {e}")
            raise

    async def get_recent_trades(
        self,
        product_id: str,
        limit: int = 100
    ) -> List[CoinbaseTrade]:
        """
        Get recent trades.
        
        Args:
            product_id: Product ID
            limit: Number of trades
            
        Returns:
            List[CoinbaseTrade]: Trade data
        """
        try:
            response = await self._request(
                method='GET',
                endpoint=f'/api/v3/brokerage/products/{product_id}/trades',
                params={'limit': limit},
                signed=True
            )
            
            trades = []
            for data in response.get('trades', []):
                trades.append(CoinbaseTrade(
                    product_id=data.get('product_id'),
                    price=float(data.get('price', 0)),
                    size=float(data.get('size', 0)),
                    side=data.get('side', ''),
                    trade_time=datetime.fromtimestamp(data.get('time', 0)),
                    trade_id=int(data.get('trade_id', 0))
                ))
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting trades for {product_id}: {e}")
            raise

    async def get_products(self) -> List[CoinbaseProductInfo]:
        """
        Get product information.
        
        Returns:
            List[CoinbaseProductInfo]: Product information
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/api/v3/brokerage/products'
            )
            
            products = []
            for data in response.get('products', []):
                product = CoinbaseProductInfo(
                    product_id=data['product_id'],
                    base_currency=data['base_currency'],
                    quote_currency=data['quote_currency'],
                    base_min_size=float(data['base_min_size']),
                    base_max_size=float(data['base_max_size']),
                    quote_increment=float(data['quote_increment']),
                    base_increment=float(data['base_increment']),
                    display_name=data['display_name'],
                    status=data.get('status', 'online'),
                    trading_disabled=data.get('trading_disabled', False)
                )
                products.append(product)
                self._product_info[product.product_id] = product
            
            return products
            
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            raise

    # =========================================================================
    # WebSocket Management
    # =========================================================================

    async def subscribe(
        self,
        config: CoinbaseStreamConfig,
        websocket: WebSocket
    ) -> None:
        """
        Subscribe to WebSocket streams.
        
        Args:
            config: Stream configuration
            websocket: WebSocket connection
        """
        try:
            stream_key = f"{'_'.join(config.product_ids)}_{'_'.join(config.channels)}"
            
            # Build subscription message
            subscribe_msg = {
                "type": "subscribe",
                "product_ids": config.product_ids,
                "channels": config.channels
            }
            
            # Add authentication if needed
            if any(c in ['user', 'full'] for c in config.channels):
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
            
            # Connect to WebSocket
            ws = await websockets.connect(self.ws_url)
            
            self._ws_connections[stream_key] = ws
            
            # Send subscription
            await ws.send(json.dumps(subscribe_msg))
            
            # Start receiving messages
            asyncio.create_task(self._receive_ws_messages(stream_key, websocket))
            
            logger.info(f"Subscribed to {stream_key}")
            
        except Exception as e:
            logger.error(f"Error subscribing to WebSocket: {e}")
            raise

    async def _receive_ws_messages(
        self,
        stream_key: str,
        websocket: WebSocket
    ) -> None:
        """Receive WebSocket messages"""
        ws = self._ws_connections.get(stream_key)
        if not ws:
            return
        
        try:
            async for message in ws:
                data = json.loads(message)
                await self._process_ws_message(stream_key, data, websocket)
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"WebSocket connection closed: {stream_key}")
        except Exception as e:
            logger.error(f"Error receiving WebSocket message: {e}")

    async def _process_ws_message(
        self,
        stream_key: str,
        data: Dict[str, Any],
        websocket: WebSocket
    ) -> None:
        """Process WebSocket message"""
        try:
            # Send to WebSocket client
            await websocket.send_json(data)
            
            # Call handlers
            if stream_key in self._stream_handlers:
                for handler in self._stream_handlers[stream_key]:
                    try:
                        handler(data)
                    except Exception as e:
                        logger.error(f"Error in stream handler: {e}")
                        
        except WebSocketDisconnect:
            logger.warning(f"WebSocket disconnected: {stream_key}")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    async def unsubscribe(self, stream_key: str) -> None:
        """
        Unsubscribe from WebSocket stream.
        
        Args:
            stream_key: Stream key
        """
        if stream_key in self._ws_connections:
            ws = self._ws_connections[stream_key]
            await ws.close()
            del self._ws_connections[stream_key]
            logger.info(f"Unsubscribed from {stream_key}")

    async def close_websockets(self) -> None:
        """Close all WebSocket connections"""
        for stream_key, ws in list(self._ws_connections.items()):
            await ws.close()
            del self._ws_connections[stream_key]
        
        logger.info("All WebSocket connections closed")

    def add_stream_handler(
        self,
        stream_key: str,
        handler
    ) -> None:
        """
        Add a handler for WebSocket stream.
        
        Args:
            stream_key: Stream key
            handler: Handler function
        """
        if stream_key not in self._stream_handlers:
            self._stream_handlers[stream_key] = []
        self._stream_handlers[stream_key].append(handler)

    def remove_stream_handler(
        self,
        stream_key: str,
        handler
    ) -> None:
        """
        Remove a handler from WebSocket stream.
        
        Args:
            stream_key: Stream key
            handler: Handler function
        """
        if stream_key in self._stream_handlers:
            self._stream_handlers[stream_key].remove(handler)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Coinbase base connection"""
        if self._session:
            await self._session.close()
            self._session = None
        
        await self.close_websockets()
        
        self._ticker_cache.clear()
        self._order_book_cache.clear()
        
        logger.info("CoinbaseBase closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/coinbase", tags=["Coinbase"])


async def get_coinbase(
    api_key: str = Query(..., description="Coinbase API Key"),
    api_secret: str = Query(..., description="Coinbase API Secret"),
    passphrase: str = Query(..., description="Coinbase Passphrase"),
    environment: CoinbaseEnvironment = Query(CoinbaseEnvironment.SANDBOX)
) -> CoinbaseBase:
    """Dependency to get CoinbaseBase instance"""
    return CoinbaseBase(api_key, api_secret, passphrase, environment)


@router.get("/ticker/{product_id}")
async def get_ticker(
    product_id: str,
    coinbase: CoinbaseBase = Depends(get_coinbase)
):
    """Get ticker for product"""
    return await coinbase.get_ticker(product_id)


@router.get("/candles/{product_id}")
async def get_candles(
    product_id: str,
    granularity: CoinbaseGranularity = Query(CoinbaseGranularity.ONE_HOUR),
    limit: int = Query(500, le=1000),
    coinbase: CoinbaseBase = Depends(get_coinbase)
):
    """Get candle data"""
    return await coinbase.get_candles(product_id, granularity, limit)


@router.get("/order-book/{product_id}")
async def get_order_book(
    product_id: str,
    level: int = Query(2, ge=1, le=3),
    coinbase: CoinbaseBase = Depends(get_coinbase)
):
    """Get order book"""
    return await coinbase.get_order_book(product_id, level)


@router.get("/trades/{product_id}")
async def get_recent_trades(
    product_id: str,
    limit: int = Query(100, le=1000),
    coinbase: CoinbaseBase = Depends(get_coinbase)
):
    """Get recent trades"""
    return await coinbase.get_recent_trades(product_id, limit)


@router.get("/products")
async def get_products(
    coinbase: CoinbaseBase = Depends(get_coinbase)
):
    """Get product information"""
    return await coinbase.get_products()


@router.websocket("/ws")
async def coinbase_websocket(
    websocket: WebSocket,
    product_ids: List[str] = Query(...),
    channels: List[str] = Query(...),
    coinbase: CoinbaseBase = Depends(get_coinbase)
):
    """WebSocket endpoint for Coinbase streams"""
    await websocket.accept()
    
    config = CoinbaseStreamConfig(
        product_ids=product_ids,
        channels=channels
    )
    
    await coinbase.subscribe(config, websocket)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await coinbase.unsubscribe(f"{'_'.join(product_ids)}_{'_'.join(channels)}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CoinbaseBase',
    'CoinbaseEnvironment',
    'CoinbaseProductType',
    'CoinbaseGranularity',
    'CoinbaseWebSocketChannel',
    'CoinbaseCandle',
    'CoinbaseTicker',
    'CoinbaseOrderBookLevel',
    'CoinbaseOrderBook',
    'CoinbaseTrade',
    'CoinbaseProductInfo',
    'CoinbaseApiLimits',
    'CoinbaseWebSocketMessage',
    'CoinbaseStreamConfig',
    'router'
]
