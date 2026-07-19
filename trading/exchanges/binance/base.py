"""
NEXUS AI TRADING SYSTEM - Binance Base Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/base.py
Description: Binance exchange base classes and utilities with full API integration
"""

import asyncio
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
from fastapi import HTTPException, status

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

class BinanceEnvironment(str, Enum):
    """Binance environment"""
    PRODUCTION = "production"
    TESTNET = "testnet"
    DEMO = "demo"


class BinanceInterval(str, Enum):
    """Binance candle intervals"""
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
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
    THREE_DAYS = "3d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class BinanceDepthLevel(str, Enum):
    """Binance depth levels"""
    LEVEL_1 = "1"
    LEVEL_5 = "5"
    LEVEL_10 = "10"
    LEVEL_20 = "20"
    LEVEL_50 = "50"
    LEVEL_100 = "100"
    LEVEL_500 = "500"
    LEVEL_1000 = "1000"


class BinanceWebSocketChannel(str, Enum):
    """Binance WebSocket channels"""
    DEPTH = "depth"
    TRADE = "trade"
    KLINE = "kline"
    TICKER = "ticker"
    BOOK_TICKER = "bookTicker"
    PARTIAL_BOOK_DEPTH = "depth"
    USER_DATA = "userData"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BinanceCandle(BaseModel):
    """Binance candle data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int
    taker_buy_volume: float
    taker_buy_quote_volume: float


class BinanceTicker(BaseModel):
    """Binance ticker data"""
    symbol: str
    price: float
    price_change: float
    price_change_pct: float
    volume: float
    quote_volume: float
    high: float
    low: float
    open: float
    close: float
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    timestamp: datetime


class BinanceOrderBookLevel(BaseModel):
    """Binance order book level"""
    price: float
    size: float


class BinanceOrderBook(BaseModel):
    """Binance order book"""
    symbol: str
    bids: List[BinanceOrderBookLevel]
    asks: List[BinanceOrderBookLevel]
    timestamp: datetime
    update_id: int


class BinanceTrade(BaseModel):
    """Binance trade data"""
    symbol: str
    price: float
    quantity: float
    quote_quantity: float
    trade_time: datetime
    is_buyer_maker: bool
    trade_id: int


class BinanceExchangeInfo(BaseModel):
    """Binance exchange information"""
    timezone: str
    server_time: datetime
    rate_limits: List[Dict[str, Any]]
    exchange_filters: List[Dict[str, Any]]
    symbols: List[Dict[str, Any]]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BinanceApiLimits:
    """Binance API limits"""
    requests_per_minute: int = 1200
    orders_per_minute: int = 50
    websocket_connections: int = 10


@dataclass
class BinanceWebSocketMessage:
    """Binance WebSocket message"""
    channel: str
    data: Dict[str, Any]
    timestamp: datetime


@dataclass
class BinanceStreamConfig:
    """Binance stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BINANCE BASE CLASS
# =============================================================================

class BinanceBase:
    """
    Binance Exchange Base Class with full API integration.
    
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

    PRODUCTION_BASE_URL = "https://api.binance.com"
    TESTNET_BASE_URL = "https://testnet.binance.vision"
    DEMO_BASE_URL = "https://api.binance.com"  # Same as production
    
    PRODUCTION_WS_URL = "wss://stream.binance.com:9443/ws"
    TESTNET_WS_URL = "wss://testnet.binance.vision/ws"
    DEMO_WS_URL = "wss://stream.binance.com:9443/ws"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: BinanceEnvironment = BinanceEnvironment.TESTNET,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BinanceBase.
        
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
        
        # Base URLs
        self.base_url = self._get_base_url()
        self.ws_url = self._get_ws_url()
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        
        # Rate limiting
        self._rate_limits = BinanceApiLimits()
        self._request_timestamps: List[float] = []
        self._order_timestamps: List[float] = []
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Exchange info
        self._exchange_info: Optional[BinanceExchangeInfo] = None
        
        # Cache
        self._ticker_cache: Dict[str, BinanceTicker] = {}
        self._order_book_cache: Dict[str, BinanceOrderBook] = {}
        
        # Stream handlers
        self._stream_handlers: Dict[str, List] = {}
        
        logger.info(f"BinanceBase initialized in {environment.value} environment")

    def _get_base_url(self) -> str:
        """Get base URL based on environment"""
        if self.environment == BinanceEnvironment.TESTNET:
            return self.TESTNET_BASE_URL
        elif self.environment == BinanceEnvironment.DEMO:
            return self.DEMO_BASE_URL
        return self.PRODUCTION_BASE_URL

    def _get_ws_url(self) -> str:
        """Get WebSocket URL based on environment"""
        if self.environment == BinanceEnvironment.TESTNET:
            return self.TESTNET_WS_URL
        elif self.environment == BinanceEnvironment.DEMO:
            return self.DEMO_WS_URL
        return self.PRODUCTION_WS_URL

    # =========================================================================
    # Session Management
    # =========================================================================

    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession(
            headers={
                'X-MBX-APIKEY': self.api_key,
                'Content-Type': 'application/json'
            },
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

    @retry_async(max_attempts=3, delay=1.0, backoff=2.0)
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        weight: int = 1
    ) -> Dict[str, Any]:
        """
        Make an API request to Binance.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request data
            signed: Whether request requires signing
            weight: Request weight for rate limiting
            
        Returns:
            Dict[str, Any]: Response data
        """
        try:
            # Check rate limits
            await self._check_rate_limits(weight)
            
            # Prepare request
            url = f"{self.base_url}{endpoint}"
            headers = {}
            
            # Add signature if required
            if signed:
                params = params or {}
                params['timestamp'] = int(time.time() * 1000)
                params['recvWindow'] = params.get('recvWindow', 5000)
                
                # Sort parameters
                query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                params['signature'] = signature
            
            # Make request
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers
            ) as response:
                # Update rate limits
                self._update_rate_limits(weight)
                
                # Parse response
                response_data = await response.json()
                
                if response.status >= 400:
                    error_msg = response_data.get('msg', 'Unknown error')
                    error_code = response_data.get('code', -1)
                    raise Exception(f"Binance API error {error_code}: {error_msg}")
                
                return response_data
                
        except asyncio.TimeoutError:
            raise Exception("Request timeout")
        except Exception as e:
            logger.error(f"API request error: {e}")
            raise

    async def _check_rate_limits(self, weight: int) -> None:
        """Check if rate limits are exceeded"""
        now = time.time()
        
        # Check requests per minute
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 60]
        if len(self._request_timestamps) + weight > self._rate_limits.requests_per_minute:
            sleep_time = 60 - (now - self._request_timestamps[0]) + 0.1
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                await self._check_rate_limits(weight)

    def _update_rate_limits(self, weight: int) -> None:
        """Update rate limit tracking"""
        now = time.time()
        self._request_timestamps.extend([now] * weight)

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature"""
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_ticker(self, symbol: str) -> BinanceTicker:
        """
        Get ticker for symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            BinanceTicker: Ticker data
        """
        try:
            # Check cache
            if symbol in self._ticker_cache:
                cached = self._ticker_cache[symbol]
                if (datetime.utcnow() - cached.timestamp).seconds < 5:
                    return cached
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/ticker/24hr',
                params={'symbol': symbol}
            )
            
            ticker = BinanceTicker(
                symbol=response['symbol'],
                price=float(response['lastPrice']),
                price_change=float(response['priceChange']),
                price_change_pct=float(response['priceChangePercent']),
                volume=float(response['volume']),
                quote_volume=float(response['quoteVolume']),
                high=float(response['highPrice']),
                low=float(response['lowPrice']),
                open=float(response['openPrice']),
                close=float(response['lastPrice']),
                bid=float(response['bidPrice']),
                ask=float(response['askPrice']),
                bid_size=float(response['bidQty']),
                ask_size=float(response['askQty']),
                timestamp=datetime.utcnow()
            )
            
            # Cache
            self._ticker_cache[symbol] = ticker
            
            return ticker
            
        except Exception as e:
            logger.error(f"Error getting ticker for {symbol}: {e}")
            raise

    async def get_candles(
        self,
        symbol: str,
        interval: BinanceInterval = BinanceInterval.ONE_HOUR,
        limit: int = 500
    ) -> List[BinanceCandle]:
        """
        Get candle data.
        
        Args:
            symbol: Symbol
            interval: Candle interval
            limit: Number of candles
            
        Returns:
            List[BinanceCandle]: Candle data
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/api/v3/klines',
                params={
                    'symbol': symbol,
                    'interval': interval.value,
                    'limit': limit
                }
            )
            
            candles = []
            for data in response:
                candles.append(BinanceCandle(
                    timestamp=datetime.fromtimestamp(data[0] / 1000),
                    open=float(data[1]),
                    high=float(data[2]),
                    low=float(data[3]),
                    close=float(data[4]),
                    volume=float(data[5]),
                    quote_volume=float(data[6]),
                    trades=int(data[8]),
                    taker_buy_volume=float(data[9]),
                    taker_buy_quote_volume=float(data[10])
                ))
            
            return candles
            
        except Exception as e:
            logger.error(f"Error getting candles for {symbol}: {e}")
            raise

    async def get_order_book(
        self,
        symbol: str,
        limit: BinanceDepthLevel = BinanceDepthLevel.LEVEL_10
    ) -> BinanceOrderBook:
        """
        Get order book.
        
        Args:
            symbol: Symbol
            limit: Depth level
            
        Returns:
            BinanceOrderBook: Order book data
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/api/v3/depth',
                params={
                    'symbol': symbol,
                    'limit': limit.value
                }
            )
            
            bids = [BinanceOrderBookLevel(price=float(b[0]), size=float(b[1])) for b in response['bids']]
            asks = [BinanceOrderBookLevel(price=float(a[0]), size=float(a[1])) for a in response['asks']]
            
            order_book = BinanceOrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=datetime.utcnow(),
                update_id=response['lastUpdateId']
            )
            
            # Cache
            self._order_book_cache[symbol] = order_book
            
            return order_book
            
        except Exception as e:
            logger.error(f"Error getting order book for {symbol}: {e}")
            raise

    async def get_exchange_info(self) -> BinanceExchangeInfo:
        """
        Get exchange information.
        
        Returns:
            BinanceExchangeInfo: Exchange information
        """
        try:
            if self._exchange_info:
                return self._exchange_info
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/exchangeInfo'
            )
            
            exchange_info = BinanceExchangeInfo(
                timezone=response['timezone'],
                server_time=datetime.fromtimestamp(response['serverTime'] / 1000),
                rate_limits=response['rateLimits'],
                exchange_filters=response['exchangeFilters'],
                symbols=response['symbols']
            )
            
            self._exchange_info = exchange_info
            
            return exchange_info
            
        except Exception as e:
            logger.error(f"Error getting exchange info: {e}")
            raise

    # =========================================================================
    # WebSocket Management
    # =========================================================================

    async def subscribe(
        self,
        symbol: str,
        channels: List[str],
        interval: Optional[str] = None,
        depth_level: Optional[str] = None
    ) -> None:
        """
        Subscribe to WebSocket streams.
        
        Args:
            symbol: Symbol
            channels: List of channels
            interval: Interval for kline channel
            depth_level: Depth level for depth channel
        """
        try:
            # Create stream key
            stream_key = f"{symbol}_{'_'.join(channels)}"
            
            # Build streams
            streams = []
            for channel in channels:
                if channel == 'depth':
                    streams.append(f"{symbol.lower()}@depth{depth_level or '10'}")
                elif channel == 'trade':
                    streams.append(f"{symbol.lower()}@trade")
                elif channel == 'kline':
                    streams.append(f"{symbol.lower()}@kline_{interval or '1m'}")
                elif channel == 'ticker':
                    streams.append(f"{symbol.lower()}@ticker")
                elif channel == 'bookTicker':
                    streams.append(f"{symbol.lower()}@bookTicker")
            
            # Connect to WebSocket
            ws_url = f"{self.ws_url}/{','.join(streams)}"
            ws = await websockets.connect(ws_url)
            
            self._ws_connections[stream_key] = ws
            
            # Start receiving messages
            asyncio.create_task(self._receive_ws_messages(stream_key))
            
            logger.info(f"Subscribed to {stream_key}")
            
        except Exception as e:
            logger.error(f"Error subscribing to WebSocket: {e}")
            raise

    async def _receive_ws_messages(self, stream_key: str) -> None:
        """Receive WebSocket messages"""
        ws = self._ws_connections.get(stream_key)
        if not ws:
            return
        
        try:
            async for message in ws:
                data = json.loads(message)
                await self._process_ws_message(stream_key, data)
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"WebSocket connection closed: {stream_key}")
        except Exception as e:
            logger.error(f"Error receiving WebSocket message: {e}")

    async def _process_ws_message(self, stream_key: str, data: Dict[str, Any]) -> None:
        """Process WebSocket message"""
        # Parse message based on stream type
        stream_type = stream_key.split('_')[1] if '_' in stream_key else 'unknown'
        
        if stream_type == 'depth':
            # Order book update
            symbol = data.get('s')
            bids = [[float(b[0]), float(b[1])] for b in data.get('b', [])]
            asks = [[float(a[0]), float(a[1])] for a in data.get('a', [])]
            # Update order book cache
            if symbol and symbol in self._order_book_cache:
                order_book = self._order_book_cache[symbol]
                # Update levels
                # ... (would need to merge updates)
                pass
        elif stream_type == 'trade':
            # Trade update
            pass
        elif stream_type == 'kline':
            # Candle update
            pass
        elif stream_type == 'ticker':
            # Ticker update
            symbol = data.get('s')
            if symbol:
                ticker = BinanceTicker(
                    symbol=symbol,
                    price=float(data.get('c', 0)),
                    price_change=float(data.get('p', 0)),
                    price_change_pct=float(data.get('P', 0)),
                    volume=float(data.get('v', 0)),
                    quote_volume=float(data.get('q', 0)),
                    high=float(data.get('h', 0)),
                    low=float(data.get('l', 0)),
                    open=float(data.get('o', 0)),
                    close=float(data.get('c', 0)),
                    bid=float(data.get('b', 0)),
                    ask=float(data.get('a', 0)),
                    bid_size=float(data.get('B', 0)),
                    ask_size=float(data.get('A', 0)),
                    timestamp=datetime.utcnow()
                )
                self._ticker_cache[symbol] = ticker
        
        # Call handlers
        if stream_key in self._stream_handlers:
            for handler in self._stream_handlers[stream_key]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Error in stream handler: {e}")

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
        """Close the Binance base connection"""
        if self._session:
            await self._session.close()
            self._session = None
        
        await self.close_websockets()
        
        self._ticker_cache.clear()
        self._order_book_cache.clear()
        
        logger.info("BinanceBase closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/v1/exchanges/binance", tags=["Binance"])


async def get_binance(
    api_key: str = Query(..., description="Binance API Key"),
    api_secret: str = Query(..., description="Binance API Secret"),
    environment: BinanceEnvironment = Query(BinanceEnvironment.TESTNET)
) -> BinanceBase:
    """Dependency to get BinanceBase instance"""
    return BinanceBase(api_key, api_secret, environment)


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    binance: BinanceBase = Depends(get_binance)
):
    """Get ticker for symbol"""
    return await binance.get_ticker(symbol)


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    interval: BinanceInterval = Query(BinanceInterval.ONE_HOUR),
    limit: int = Query(500, le=1000),
    binance: BinanceBase = Depends(get_binance)
):
    """Get candle data"""
    return await binance.get_candles(symbol, interval, limit)


@router.get("/order-book/{symbol}")
async get_order_book(
    symbol: str,
    limit: BinanceDepthLevel = Query(BinanceDepthLevel.LEVEL_10),
    binance: BinanceBase = Depends(get_binance)
):
    """Get order book"""
    return await binance.get_order_book(symbol, limit)


@router.get("/exchange-info")
async def get_exchange_info(
    binance: BinanceBase = Depends(get_binance)
):
    """Get exchange information"""
    return await binance.get_exchange_info()


@router.websocket("/ws/{symbol}")
async def binance_websocket(
    websocket: WebSocket,
    symbol: str,
    channels: List[str] = Query(...),
    interval: str = Query(None),
    depth: str = Query(None)
):
    """WebSocket endpoint for Binance streams"""
    await websocket.accept()
    
    # Create Binance instance
    binance = BinanceBase(
        api_key=config.API_KEY,
        api_secret=config.API_SECRET
    )
    
    # Subscribe
    stream_key = f"{symbol}_{'_'.join(channels)}"
    await binance.subscribe(symbol, channels, interval, depth)
    
    try:
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await binance.unsubscribe(stream_key)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BinanceBase',
    'BinanceEnvironment',
    'BinanceInterval',
    'BinanceDepthLevel',
    'BinanceWebSocketChannel',
    'BinanceCandle',
    'BinanceTicker',
    'BinanceOrderBookLevel',
    'BinanceOrderBook',
    'BinanceTrade',
    'BinanceExchangeInfo',
    'BinanceApiLimits',
    'BinanceWebSocketMessage',
    'BinanceStreamConfig',
    'router'
]
