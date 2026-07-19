"""
NEXUS AI TRADING SYSTEM - Bybit Base Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/base.py
Description: Bybit exchange base classes and utilities with full API integration
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

class BybitEnvironment(str, Enum):
    """Bybit environment"""
    PRODUCTION = "production"
    TESTNET = "testnet"
    DEMO = "demo"


class BybitInterval(str, Enum):
    """Bybit candle intervals"""
    ONE_MINUTE = "1"
    THREE_MINUTES = "3"
    FIVE_MINUTES = "5"
    FIFTEEN_MINUTES = "15"
    THIRTY_MINUTES = "30"
    ONE_HOUR = "60"
    TWO_HOURS = "120"
    FOUR_HOURS = "240"
    SIX_HOURS = "360"
    TWELVE_HOURS = "720"
    ONE_DAY = "D"
    ONE_WEEK = "W"
    ONE_MONTH = "M"


class BybitCategory(str, Enum):
    """Bybit categories"""
    SPOT = "spot"
    LINEAR = "linear"  # USDT perpetual
    INVERSE = "inverse"  # Coin-margined
    OPTION = "option"


class BybitDepthLevel(str, Enum):
    """Bybit depth levels"""
    LEVEL_1 = "1"
    LEVEL_5 = "5"
    LEVEL_10 = "10"
    LEVEL_20 = "20"
    LEVEL_50 = "50"


class BybitWebSocketChannel(str, Enum):
    """Bybit WebSocket channels"""
    ORDER_BOOK = "orderbook"
    TRADE = "trade"
    KLINE = "kline"
    TICKER = "ticker"
    BOOK_TICKER = "bookticker"
    POSITION = "position"
    ORDER = "order"
    EXECUTION = "execution"
    WALLET = "wallet"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BybitCandle(BaseModel):
    """Bybit candle data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float


class BybitTicker(BaseModel):
    """Bybit ticker data"""
    symbol: str
    price: float
    price_change: float
    price_change_pct: float
    volume: float
    turnover: float
    high: float
    low: float
    open: float
    close: float
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    timestamp: datetime


class BybitOrderBookLevel(BaseModel):
    """Bybit order book level"""
    price: float
    size: float


class BybitOrderBook(BaseModel):
    """Bybit order book"""
    symbol: str
    bids: List[BybitOrderBookLevel]
    asks: List[BybitOrderBookLevel]
    timestamp: datetime
    update_id: int


class BybitTrade(BaseModel):
    """Bybit trade data"""
    symbol: str
    price: float
    quantity: float
    trade_time: datetime
    side: str
    trade_id: str


class BybitInstrumentInfo(BaseModel):
    """Bybit instrument information"""
    symbol: str
    base_currency: str
    quote_currency: str
    contract_type: str
    status: str
    min_order_qty: float
    max_order_qty: float
    qty_step: float
    min_price: float
    max_price: float
    price_step: float
    leverage: int


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BybitApiLimits:
    """Bybit API limits"""
    requests_per_second: int = 50
    orders_per_second: int = 10
    websocket_connections: int = 10


@dataclass
class BybitWebSocketMessage:
    """Bybit WebSocket message"""
    topic: str
    data: Dict[str, Any]
    timestamp: datetime


@dataclass
class BybitStreamConfig:
    """Bybit stream configuration"""
    symbol: str
    category: BybitCategory
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BYBIT BASE CLASS
# =============================================================================

class BybitBase:
    """
    Bybit Exchange Base Class with full API integration.
    
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

    PRODUCTION_BASE_URL = "https://api.bybit.com"
    TESTNET_BASE_URL = "https://api-testnet.bybit.com"
    DEMO_BASE_URL = "https://api-demo.bybit.com"
    
    PRODUCTION_WS_URL = "wss://stream.bybit.com/v5/public/linear"
    TESTNET_WS_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
    DEMO_WS_URL = "wss://stream-demo.bybit.com/v5/public/linear"
    
    PRODUCTION_PRIVATE_WS_URL = "wss://stream.bybit.com/v5/private"
    TESTNET_PRIVATE_WS_URL = "wss://stream-testnet.bybit.com/v5/private"
    DEMO_PRIVATE_WS_URL = "wss://stream-demo.bybit.com/v5/private"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: BybitEnvironment = BybitEnvironment.TESTNET,
        category: BybitCategory = BybitCategory.LINEAR,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BybitBase.
        
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
        
        # Base URLs
        self.base_url = self._get_base_url()
        self.ws_url = self._get_ws_url()
        self.private_ws_url = self._get_private_ws_url()
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        
        # Rate limiting
        self._rate_limits = BybitApiLimits()
        self._request_timestamps: List[float] = []
        self._order_timestamps: List[float] = []
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Instrument info
        self._instrument_info: Dict[str, BybitInstrumentInfo] = {}
        
        # Cache
        self._ticker_cache: Dict[str, BybitTicker] = {}
        self._order_book_cache: Dict[str, BybitOrderBook] = {}
        
        # Stream handlers
        self._stream_handlers: Dict[str, List] = {}
        
        # WebSocket manager
        self._ws_manager = WebSocketManager()
        
        logger.info(f"BybitBase initialized in {environment.value} environment")

    def _get_base_url(self) -> str:
        """Get base URL based on environment"""
        if self.environment == BybitEnvironment.TESTNET:
            return self.TESTNET_BASE_URL
        elif self.environment == BybitEnvironment.DEMO:
            return self.DEMO_BASE_URL
        return self.PRODUCTION_BASE_URL

    def _get_ws_url(self) -> str:
        """Get WebSocket URL based on environment"""
        if self.environment == BybitEnvironment.TESTNET:
            return self.TESTNET_WS_URL
        elif self.environment == BybitEnvironment.DEMO:
            return self.DEMO_WS_URL
        return self.PRODUCTION_WS_URL

    def _get_private_ws_url(self) -> str:
        """Get private WebSocket URL based on environment"""
        if self.environment == BybitEnvironment.TESTNET:
            return self.TESTNET_PRIVATE_WS_URL
        elif self.environment == BybitEnvironment.DEMO:
            return self.DEMO_PRIVATE_WS_URL
        return self.PRODUCTION_PRIVATE_WS_URL

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
        signed: bool = False,
        recv_window: int = 5000
    ) -> Dict[str, Any]:
        """
        Make an API request to Bybit.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request data
            signed: Whether request requires signing
            recv_window: Receive window
            
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
                timestamp = str(int(time.time() * 1000))
                headers['X-BAPI-API-KEY'] = self.api_key
                headers['X-BAPI-TIMESTAMP'] = timestamp
                headers['X-BAPI-RECV-WINDOW'] = str(recv_window)
                
                # Build query string
                query_string = ''
                if method == 'GET' and params:
                    query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                elif method == 'POST' and data:
                    query_string = json.dumps(data, separators=(',', ':'))
                
                # Generate signature
                signature_payload = timestamp + self.api_key + recv_window + query_string
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    signature_payload.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                headers['X-BAPI-SIGN'] = signature
            
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
                    error_msg = response_data.get('retMsg', 'Unknown error')
                    error_code = response_data.get('retCode', -1)
                    raise Exception(f"Bybit API error {error_code}: {error_msg}")
                
                if response_data.get('retCode') != 0:
                    raise Exception(f"Bybit API error: {response_data.get('retMsg')}")
                
                return response_data.get('result', {})
                
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
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_ticker(self, symbol: str) -> BybitTicker:
        """
        Get ticker for symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            BybitTicker: Ticker data
        """
        try:
            # Check cache
            if symbol in self._ticker_cache:
                cached = self._ticker_cache[symbol]
                if (datetime.utcnow() - cached.timestamp).seconds < 5:
                    return cached
            
            params = {
                'category': self.category.value,
                'symbol': symbol
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/tickers',
                params=params
            )
            
            if not response.get('list'):
                raise ValueError(f"No ticker data for {symbol}")
            
            data = response['list'][0]
            
            ticker = BybitTicker(
                symbol=data['symbol'],
                price=float(data['lastPrice']),
                price_change=float(data['price24hPcnt']) * float(data['lastPrice']),
                price_change_pct=float(data['price24hPcnt']) * 100,
                volume=float(data['volume24h']),
                turnover=float(data['turnover24h']),
                high=float(data['highPrice24h']),
                low=float(data['lowPrice24h']),
                open=float(data['openPrice24h']),
                close=float(data['lastPrice']),
                bid=float(data['bid1Price']),
                ask=float(data['ask1Price']),
                bid_size=float(data['bid1Size']),
                ask_size=float(data['ask1Size']),
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
        interval: BybitInterval = BybitInterval.ONE_HOUR,
        limit: int = 500
    ) -> List[BybitCandle]:
        """
        Get candle data.
        
        Args:
            symbol: Symbol
            interval: Candle interval
            limit: Number of candles
            
        Returns:
            List[BybitCandle]: Candle data
        """
        try:
            params = {
                'category': self.category.value,
                'symbol': symbol,
                'interval': interval.value,
                'limit': limit
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/kline',
                params=params
            )
            
            candles = []
            for data in response.get('list', []):
                candles.append(BybitCandle(
                    timestamp=datetime.fromtimestamp(int(data[0]) / 1000),
                    open=float(data[1]),
                    high=float(data[2]),
                    low=float(data[3]),
                    close=float(data[4]),
                    volume=float(data[5]),
                    turnover=float(data[6])
                ))
            
            return candles
            
        except Exception as e:
            logger.error(f"Error getting candles for {symbol}: {e}")
            raise

    async def get_order_book(
        self,
        symbol: str,
        limit: BybitDepthLevel = BybitDepthLevel.LEVEL_10
    ) -> BybitOrderBook:
        """
        Get order book.
        
        Args:
            symbol: Symbol
            limit: Depth level
            
        Returns:
            BybitOrderBook: Order book data
        """
        try:
            params = {
                'category': self.category.value,
                'symbol': symbol,
                'limit': limit.value
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/orderbook',
                params=params
            )
            
            bids = [BybitOrderBookLevel(price=float(b[0]), size=float(b[1])) for b in response['b']]
            asks = [BybitOrderBookLevel(price=float(a[0]), size=float(a[1])) for a in response['a']]
            
            order_book = BybitOrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=datetime.utcnow(),
                update_id=int(response.get('u', 0))
            )
            
            # Cache
            self._order_book_cache[symbol] = order_book
            
            return order_book
            
        except Exception as e:
            logger.error(f"Error getting order book for {symbol}: {e}")
            raise

    async def get_recent_trades(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[BybitTrade]:
        """
        Get recent trades.
        
        Args:
            symbol: Symbol
            limit: Number of trades
            
        Returns:
            List[BybitTrade]: Trade data
        """
        try:
            params = {
                'category': self.category.value,
                'symbol': symbol,
                'limit': limit
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/recent-trade',
                params=params
            )
            
            trades = []
            for data in response.get('list', []):
                trades.append(BybitTrade(
                    symbol=data['symbol'],
                    price=float(data['price']),
                    quantity=float(data['size']),
                    trade_time=datetime.fromtimestamp(int(data['time']) / 1000),
                    side=data['side'].lower(),
                    trade_id=data['tradeId']
                ))
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting trades for {symbol}: {e}")
            raise

    async def get_instruments(self) -> List[BybitInstrumentInfo]:
        """
        Get instrument information.
        
        Returns:
            List[BybitInstrumentInfo]: Instrument information
        """
        try:
            params = {
                'category': self.category.value
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/instruments-info',
                params=params
            )
            
            instruments = []
            for data in response.get('list', []):
                instrument = BybitInstrumentInfo(
                    symbol=data['symbol'],
                    base_currency=data.get('baseCoin', ''),
                    quote_currency=data.get('quoteCoin', ''),
                    contract_type=data.get('contractType', ''),
                    status=data.get('status', ''),
                    min_order_qty=float(data.get('lotSizeFilter', {}).get('minOrderQty', 0)),
                    max_order_qty=float(data.get('lotSizeFilter', {}).get('maxOrderQty', 0)),
                    qty_step=float(data.get('lotSizeFilter', {}).get('qtyStep', 0)),
                    min_price=float(data.get('priceFilter', {}).get('minPrice', 0)),
                    max_price=float(data.get('priceFilter', {}).get('maxPrice', 0)),
                    price_step=float(data.get('priceFilter', {}).get('tickSize', 0)),
                    leverage=int(data.get('leverageFilter', {}).get('maxLeverage', 1))
                )
                instruments.append(instrument)
                self._instrument_info[instrument.symbol] = instrument
            
            return instruments
            
        except Exception as e:
            logger.error(f"Error getting instruments: {e}")
            raise

    # =========================================================================
    # WebSocket Management
    # =========================================================================

    async def subscribe(
        self,
        config: BybitStreamConfig,
        websocket: WebSocket
    ) -> None:
        """
        Subscribe to WebSocket streams.
        
        Args:
            config: Stream configuration
            websocket: WebSocket connection
        """
        try:
            stream_key = f"{config.symbol}_{'_'.join(config.channels)}"
            
            # Build subscription message
            args = []
            for channel in config.channels:
                if channel == 'orderbook':
                    depth = config.depth_level or '10'
                    args.append(f"{channel}.{depth}.{config.symbol}")
                elif channel == 'kline':
                    interval = config.interval or '1'
                    args.append(f"{channel}.{interval}.{config.symbol}")
                else:
                    args.append(f"{channel}.{config.symbol}")
            
            # Connect to WebSocket
            ws_url = f"{self.ws_url}?category={config.category.value}"
            ws = await websockets.connect(ws_url)
            
            self._ws_connections[stream_key] = ws
            
            # Send subscription
            subscribe_msg = {
                "op": "subscribe",
                "args": args
            }
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
        """Close the Bybit base connection"""
        if self._session:
            await self._session.close()
            self._session = None
        
        await self.close_websockets()
        
        self._ticker_cache.clear()
        self._order_book_cache.clear()
        
        logger.info("BybitBase closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/bybit", tags=["Bybit"])


async def get_bybit(
    api_key: str = Query(..., description="Bybit API Key"),
    api_secret: str = Query(..., description="Bybit API Secret"),
    environment: BybitEnvironment = Query(BybitEnvironment.TESTNET),
    category: BybitCategory = Query(BybitCategory.LINEAR)
) -> BybitBase:
    """Dependency to get BybitBase instance"""
    return BybitBase(api_key, api_secret, environment, category)


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    bybit: BybitBase = Depends(get_bybit)
):
    """Get ticker for symbol"""
    return await bybit.get_ticker(symbol)


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    interval: BybitInterval = Query(BybitInterval.ONE_HOUR),
    limit: int = Query(500, le=1000),
    bybit: BybitBase = Depends(get_bybit)
):
    """Get candle data"""
    return await bybit.get_candles(symbol, interval, limit)


@router.get("/order-book/{symbol}")
async def get_order_book(
    symbol: str,
    limit: BybitDepthLevel = Query(BybitDepthLevel.LEVEL_10),
    bybit: BybitBase = Depends(get_bybit)
):
    """Get order book"""
    return await bybit.get_order_book(symbol, limit)


@router.get("/trades/{symbol}")
async def get_recent_trades(
    symbol: str,
    limit: int = Query(100, le=1000),
    bybit: BybitBase = Depends(get_bybit)
):
    """Get recent trades"""
    return await bybit.get_recent_trades(symbol, limit)


@router.get("/instruments")
async def get_instruments(
    bybit: BybitBase = Depends(get_bybit)
):
    """Get instrument information"""
    return await bybit.get_instruments()


@router.websocket("/ws/{symbol}")
async def bybit_websocket(
    websocket: WebSocket,
    symbol: str,
    category: BybitCategory = Query(BybitCategory.LINEAR),
    channels: List[str] = Query(...),
    interval: str = Query(None),
    depth: str = Query(None)
):
    """WebSocket endpoint for Bybit streams"""
    await websocket.accept()
    
    config = BybitStreamConfig(
        symbol=symbol,
        category=category,
        channels=channels,
        interval=interval,
        depth_level=depth
    )
    
    bybit = BybitBase("", "", BybitEnvironment.TESTNET, category)
    await bybit.subscribe(config, websocket)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await bybit.unsubscribe(f"{symbol}_{'_'.join(channels)}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitBase',
    'BybitEnvironment',
    'BybitInterval',
    'BybitCategory',
    'BybitDepthLevel',
    'BybitWebSocketChannel',
    'BybitCandle',
    'BybitTicker',
    'BybitOrderBookLevel',
    'BybitOrderBook',
    'BybitTrade',
    'BybitInstrumentInfo',
    'BybitApiLimits',
    'BybitWebSocketMessage',
    'BybitStreamConfig',
    'router'
]
