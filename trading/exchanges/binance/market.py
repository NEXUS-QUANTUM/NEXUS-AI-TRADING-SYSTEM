"""
NEXUS AI TRADING SYSTEM - Binance Market Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/market.py
Description: Binance market data with full API integration
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import aiohttp
import pandas as pd
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status, WebSocket, WebSocketDisconnect

# NEXUS Internal Imports
from shared.configs.exchange_config import ExchangeConfig
from shared.constants.trading_constants import TIME_FRAMES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.websocket_manager import WebSocketManager

# Binance imports
from trading.exchanges.binance.base import (
    BinanceBase,
    BinanceEnvironment,
    BinanceInterval,
    BinanceDepthLevel,
    BinanceCandle,
    BinanceTicker,
    BinanceOrderBook,
    BinanceTrade,
    BinanceExchangeInfo
)
from trading.exchanges.binance.exceptions import (
    BinanceException,
    BinanceMarketError,
    BinanceErrorCode,
    BinanceErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BinanceMarketType(str, Enum):
    """Binance market types"""
    SPOT = "spot"
    FUTURES = "futures"
    MARGIN = "margin"


class BinanceSymbolStatus(str, Enum):
    """Binance symbol status"""
    TRADING = "TRADING"
    BREAK = "BREAK"
    HALT = "HALT"
    CLOSED = "CLOSED"


class BinanceKlineInterval(str, Enum):
    """Binance kline intervals"""
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


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BinanceSymbolInfo(BaseModel):
    """Binance symbol information"""
    symbol: str
    status: BinanceSymbolStatus
    base_asset: str
    quote_asset: str
    base_precision: int
    quote_precision: int
    min_qty: float
    max_qty: float
    step_size: float
    min_price: float
    max_price: float
    tick_size: float
    filters: Dict[str, Any]


class BinanceMarketDataRequest(BaseModel):
    """Request model for market data"""
    symbol: str
    market_type: BinanceMarketType = BinanceMarketType.SPOT
    interval: BinanceKlineInterval = BinanceKlineInterval.ONE_HOUR
    limit: int = 500
    include_order_book: bool = True
    include_trades: bool = True
    include_ticker: bool = True


class BinanceMarketDataResponse(BaseModel):
    """Response model for market data"""
    symbol: str
    market_type: BinanceMarketType
    timestamp: datetime
    ticker: Optional[BinanceTicker] = None
    candles: List[BinanceCandle]
    order_book: Optional[BinanceOrderBook] = None
    trades: List[BinanceTrade]
    symbol_info: Optional[BinanceSymbolInfo] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BinanceMarketStreamConfig:
    """Binance market stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BINANCE MARKET
# =============================================================================

class BinanceMarket:
    """
    Binance Market Data with full API integration.
    
    Features:
    - Real-time market data
    - Order book data
    - Trade data
    - Candle data
    - Ticker data
    - WebSocket streaming
    - Symbol information
    - Multiple market types
    """

    def __init__(
        self,
        config: Optional[ExchangeConfig] = None,
        environment: BinanceEnvironment = BinanceEnvironment.TESTNET
    ):
        """
        Initialize BinanceMarket.
        
        Args:
            config: Exchange configuration
            environment: Binance environment
        """
        self.config = config or ExchangeConfig()
        self.environment = environment
        
        # Base URLs
        if environment == BinanceEnvironment.TESTNET:
            self.base_url = "https://testnet.binance.vision"
            self.ws_url = "wss://testnet.binance.vision/ws"
        else:
            self.base_url = "https://api.binance.com"
            self.ws_url = "wss://stream.binance.com:9443/ws"
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # WebSocket manager
        self._ws_manager = WebSocketManager()
        self._ws_connections: Dict[str, WebSocket] = {}
        self._ws_subscriptions: Dict[str, List[str]] = {}
        
        # Cache
        self._symbol_info_cache: Dict[str, BinanceSymbolInfo] = {}
        self._ticker_cache: Dict[str, BinanceTicker] = {}
        self._order_book_cache: Dict[str, BinanceOrderBook] = {}
        
        # Error handler
        self._error_handler = BinanceErrorHandler()
        
        # Stream handlers
        self._stream_handlers: Dict[str, List] = {}
        
        logger.info(f"BinanceMarket initialized in {environment.value}")

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
        
        await self._close_websockets()

    # =========================================================================
    # API Request Methods
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        market_type: BinanceMarketType = BinanceMarketType.SPOT
    ) -> Dict[str, Any]:
        """
        Make an API request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            market_type: Market type
            
        Returns:
            Dict[str, Any]: Response data
        """
        try:
            # Determine base URL based on market type
            if market_type == BinanceMarketType.FUTURES:
                base = "https://fapi.binance.com" if self.environment != BinanceEnvironment.TESTNET else "https://testnet.binancefuture.com"
            elif market_type == BinanceMarketType.MARGIN:
                base = self.base_url
            else:
                base = self.base_url
            
            url = f"{base}{endpoint}"
            
            async with self._session.request(
                method=method,
                url=url,
                params=params
            ) as response:
                data = await response.json()
                
                if response.status >= 400:
                    error_msg = data.get('msg', 'Unknown error')
                    error_code = data.get('code', -1)
                    raise BinanceException(
                        code=BinanceErrorCode(error_code) if error_code in BinanceErrorCode.__members__ else BinanceErrorCode.UNKNOWN,
                        message=error_msg,
                        data={'status': response.status, 'response': data}
                    )
                
                return data
                
        except BinanceException:
            raise
        except Exception as e:
            logger.error(f"API request error: {e}")
            raise BinanceMarketError(
                code=BinanceErrorCode.UNKNOWN,
                message=f"Market data request failed: {str(e)}"
            )

    # =========================================================================
    # Symbol Information
    # =========================================================================

    async def get_symbol_info(
        self,
        symbol: str,
        market_type: BinanceMarketType = BinanceMarketType.SPOT
    ) -> BinanceSymbolInfo:
        """
        Get symbol information.
        
        Args:
            symbol: Symbol
            market_type: Market type
            
        Returns:
            BinanceSymbolInfo: Symbol information
        """
        try:
            # Check cache
            cache_key = f"{market_type.value}_{symbol}"
            if cache_key in self._symbol_info_cache:
                return self._symbol_info_cache[cache_key]
            
            # Get exchange info
            response = await self._request(
                method='GET',
                endpoint='/api/v3/exchangeInfo' if market_type != BinanceMarketType.FUTURES else '/fapi/v1/exchangeInfo',
                market_type=market_type
            )
            
            # Find symbol
            symbol_data = None
            for s in response.get('symbols', []):
                if s.get('symbol') == symbol:
                    symbol_data = s
                    break
            
            if not symbol_data:
                raise BinanceMarketError(
                    code=BinanceErrorCode.INVALID_SYMBOL,
                    message=f"Symbol {symbol} not found"
                )
            
            # Parse filters
            filters = {}
            for f in symbol_data.get('filters', []):
                filter_type = f.get('filterType')
                if filter_type == 'PRICE_FILTER':
                    filters['min_price'] = float(f.get('minPrice', 0))
                    filters['max_price'] = float(f.get('maxPrice', 0))
                    filters['tick_size'] = float(f.get('tickSize', 0))
                elif filter_type == 'LOT_SIZE':
                    filters['min_qty'] = float(f.get('minQty', 0))
                    filters['max_qty'] = float(f.get('maxQty', 0))
                    filters['step_size'] = float(f.get('stepSize', 0))
            
            symbol_info = BinanceSymbolInfo(
                symbol=symbol_data.get('symbol'),
                status=BinanceSymbolStatus(symbol_data.get('status', 'CLOSED')),
                base_asset=symbol_data.get('baseAsset'),
                quote_asset=symbol_data.get('quoteAsset'),
                base_precision=symbol_data.get('baseAssetPrecision', 8),
                quote_precision=symbol_data.get('quoteAssetPrecision', 8),
                min_qty=filters.get('min_qty', 0.000001),
                max_qty=filters.get('max_qty', 10000000),
                step_size=filters.get('step_size', 0.000001),
                min_price=filters.get('min_price', 0.000001),
                max_price=filters.get('max_price', 10000000),
                tick_size=filters.get('tick_size', 0.000001),
                filters=filters
            )
            
            # Cache
            self._symbol_info_cache[cache_key] = symbol_info
            
            return symbol_info
            
        except Exception as e:
            logger.error(f"Error getting symbol info: {e}")
            raise

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_market_data(
        self,
        request: BinanceMarketDataRequest
    ) -> BinanceMarketDataResponse:
        """
        Get comprehensive market data.
        
        Args:
            request: Market data request
            
        Returns:
            BinanceMarketDataResponse: Market data
        """
        try:
            # Get symbol info
            symbol_info = await self.get_symbol_info(
                request.symbol,
                request.market_type
            )
            
            # Get ticker
            ticker = None
            if request.include_ticker:
                ticker = await self.get_ticker(request.symbol, request.market_type)
            
            # Get candles
            candles = await self.get_candles(
                request.symbol,
                request.interval,
                request.limit,
                request.market_type
            )
            
            # Get order book
            order_book = None
            if request.include_order_book:
                order_book = await self.get_order_book(
                    request.symbol,
                    request.market_type
                )
            
            # Get trades
            trades = []
            if request.include_trades:
                trades = await self.get_recent_trades(
                    request.symbol,
                    limit=100,
                    market_type=request.market_type
                )
            
            return BinanceMarketDataResponse(
                symbol=request.symbol,
                market_type=request.market_type,
                timestamp=datetime.utcnow(),
                ticker=ticker,
                candles=candles,
                order_book=order_book,
                trades=trades,
                symbol_info=symbol_info
            )
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            raise

    # =========================================================================
    # Ticker
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_ticker(
        self,
        symbol: str,
        market_type: BinanceMarketType = BinanceMarketType.SPOT
    ) -> BinanceTicker:
        """
        Get ticker for symbol.
        
        Args:
            symbol: Symbol
            market_type: Market type
            
        Returns:
            BinanceTicker: Ticker data
        """
        try:
            # Check cache
            cache_key = f"{market_type.value}_{symbol}"
            if cache_key in self._ticker_cache:
                cached = self._ticker_cache[cache_key]
                if (datetime.utcnow() - cached.timestamp).seconds < 5:
                    return cached
            
            endpoint = '/api/v3/ticker/24hr' if market_type != BinanceMarketType.FUTURES else '/fapi/v1/ticker/24hr'
            
            response = await self._request(
                method='GET',
                endpoint=endpoint,
                params={'symbol': symbol},
                market_type=market_type
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
                bid=float(response.get('bidPrice', 0)),
                ask=float(response.get('askPrice', 0)),
                bid_size=float(response.get('bidQty', 0)),
                ask_size=float(response.get('askQty', 0)),
                timestamp=datetime.utcnow()
            )
            
            # Cache
            self._ticker_cache[cache_key] = ticker
            
            return ticker
            
        except Exception as e:
            logger.error(f"Error getting ticker for {symbol}: {e}")
            raise

    # =========================================================================
    # Candles
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_candles(
        self,
        symbol: str,
        interval: BinanceKlineInterval = BinanceKlineInterval.ONE_HOUR,
        limit: int = 500,
        market_type: BinanceMarketType = BinanceMarketType.SPOT
    ) -> List[BinanceCandle]:
        """
        Get candle data.
        
        Args:
            symbol: Symbol
            interval: Candle interval
            limit: Number of candles
            market_type: Market type
            
        Returns:
            List[BinanceCandle]: Candle data
        """
        try:
            endpoint = '/api/v3/klines' if market_type != BinanceMarketType.FUTURES else '/fapi/v1/klines'
            
            response = await self._request(
                method='GET',
                endpoint=endpoint,
                params={
                    'symbol': symbol,
                    'interval': interval.value,
                    'limit': limit
                },
                market_type=market_type
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

    # =========================================================================
    # Order Book
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order_book(
        self,
        symbol: str,
        market_type: BinanceMarketType = BinanceMarketType.SPOT,
        limit: BinanceDepthLevel = BinanceDepthLevel.LEVEL_10
    ) -> BinanceOrderBook:
        """
        Get order book.
        
        Args:
            symbol: Symbol
            market_type: Market type
            limit: Depth level
            
        Returns:
            BinanceOrderBook: Order book data
        """
        try:
            # Check cache
            cache_key = f"{market_type.value}_{symbol}"
            if cache_key in self._order_book_cache:
                cached = self._order_book_cache[cache_key]
                if (datetime.utcnow() - cached.timestamp).seconds < 5:
                    return cached
            
            endpoint = '/api/v3/depth' if market_type != BinanceMarketType.FUTURES else '/fapi/v1/depth'
            
            response = await self._request(
                method='GET',
                endpoint=endpoint,
                params={
                    'symbol': symbol,
                    'limit': limit.value
                },
                market_type=market_type
            )
            
            from trading.exchanges.binance.base import BinanceOrderBookLevel
            
            bids = [BinanceOrderBookLevel(price=float(b[0]), size=float(b[1])) for b in response['bids']]
            asks = [BinanceOrderBookLevel(price=float(a[0]), size=float(a[1])) for a in response['asks']]
            
            order_book = BinanceOrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=datetime.utcnow(),
                update_id=response.get('lastUpdateId', 0)
            )
            
            # Cache
            self._order_book_cache[cache_key] = order_book
            
            return order_book
            
        except Exception as e:
            logger.error(f"Error getting order book for {symbol}: {e}")
            raise

    # =========================================================================
    # Trades
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_recent_trades(
        self,
        symbol: str,
        limit: int = 100,
        market_type: BinanceMarketType = BinanceMarketType.SPOT
    ) -> List[BinanceTrade]:
        """
        Get recent trades.
        
        Args:
            symbol: Symbol
            limit: Number of trades
            market_type: Market type
            
        Returns:
            List[BinanceTrade]: Trade data
        """
        try:
            endpoint = '/api/v3/trades' if market_type != BinanceMarketType.FUTURES else '/fapi/v1/trades'
            
            response = await self._request(
                method='GET',
                endpoint=endpoint,
                params={
                    'symbol': symbol,
                    'limit': limit
                },
                market_type=market_type
            )
            
            trades = []
            for data in response:
                trades.append(BinanceTrade(
                    symbol=data['symbol'],
                    price=float(data['price']),
                    quantity=float(data['qty']),
                    quote_quantity=float(data['quoteQty']),
                    trade_time=datetime.fromtimestamp(data['time'] / 1000),
                    is_buyer_maker=data['isBuyerMaker'],
                    trade_id=data['id']
                ))
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting trades for {symbol}: {e}")
            raise

    # =========================================================================
    # All Symbols
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_all_symbols(
        self,
        market_type: BinanceMarketType = BinanceMarketType.SPOT
    ) -> List[str]:
        """
        Get all symbols.
        
        Args:
            market_type: Market type
            
        Returns:
            List[str]: List of symbols
        """
        try:
            endpoint = '/api/v3/exchangeInfo' if market_type != BinanceMarketType.FUTURES else '/fapi/v1/exchangeInfo'
            
            response = await self._request(
                method='GET',
                endpoint=endpoint,
                market_type=market_type
            )
            
            symbols = []
            for s in response.get('symbols', []):
                if s.get('status') == 'TRADING':
                    symbols.append(s.get('symbol'))
            
            return symbols
            
        except Exception as e:
            logger.error(f"Error getting all symbols: {e}")
            raise

    # =========================================================================
    # WebSocket Streaming
    # =========================================================================

    async def subscribe(
        self,
        config: BinanceMarketStreamConfig,
        websocket: WebSocket
    ) -> None:
        """
        Subscribe to market streams.
        
        Args:
            config: Stream configuration
            websocket: WebSocket connection
        """
        try:
            stream_key = f"{config.symbol}_{'_'.join(config.channels)}"
            
            # Build streams
            streams = []
            for channel in config.channels:
                if channel == 'depth':
                    streams.append(f"{config.symbol.lower()}@depth{config.depth_level or '10'}")
                elif channel == 'trade':
                    streams.append(f"{config.symbol.lower()}@trade")
                elif channel == 'kline':
                    streams.append(f"{config.symbol.lower()}@kline_{config.interval or '1m'}")
                elif channel == 'ticker':
                    streams.append(f"{config.symbol.lower()}@ticker")
                elif channel == 'bookTicker':
                    streams.append(f"{config.symbol.lower()}@bookTicker")
            
            # Connect to WebSocket
            ws_url = f"{self.ws_url}/{','.join(streams)}"
            ws = await websockets.connect(ws_url)
            
            self._ws_connections[stream_key] = ws
            self._ws_subscriptions[stream_key] = config.channels
            
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
        Unsubscribe from stream.
        
        Args:
            stream_key: Stream key
        """
        if stream_key in self._ws_connections:
            ws = self._ws_connections[stream_key]
            await ws.close()
            del self._ws_connections[stream_key]
            if stream_key in self._ws_subscriptions:
                del self._ws_subscriptions[stream_key]
            logger.info(f"Unsubscribed from {stream_key}")

    async def _close_websockets(self) -> None:
        """Close all WebSocket connections"""
        for stream_key in list(self._ws_connections.keys()):
            await self.unsubscribe(stream_key)

    def add_stream_handler(
        self,
        stream_key: str,
        handler
    ) -> None:
        """Add stream handler"""
        if stream_key not in self._stream_handlers:
            self._stream_handlers[stream_key] = []
        self._stream_handlers[stream_key].append(handler)

    def remove_stream_handler(
        self,
        stream_key: str,
        handler
    ) -> None:
        """Remove stream handler"""
        if stream_key in self._stream_handlers:
            self._stream_handlers[stream_key].remove(handler)

    # =========================================================================
    # Data Export
    # =========================================================================

    async def export_candles_to_csv(
        self,
        symbol: str,
        interval: BinanceKlineInterval,
        limit: int = 500,
        market_type: BinanceMarketType = BinanceMarketType.SPOT,
        filename: Optional[str] = None
    ) -> str:
        """
        Export candles to CSV.
        
        Args:
            symbol: Symbol
            interval: Candle interval
            limit: Number of candles
            market_type: Market type
            filename: Output filename
            
        Returns:
            str: Filename
        """
        try:
            candles = await self.get_candles(symbol, interval, limit, market_type)
            
            data = []
            for c in candles:
                data.append({
                    'timestamp': c.timestamp.isoformat(),
                    'open': c.open,
                    'high': c.high,
                    'low': c.low,
                    'close': c.close,
                    'volume': c.volume,
                    'quote_volume': c.quote_volume,
                    'trades': c.trades
                })
            
            df = pd.DataFrame(data)
            
            if not filename:
                filename = f"{symbol}_{interval.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            
            df.to_csv(filename, index=False)
            return filename
            
        except Exception as e:
            logger.error(f"Error exporting candles: {e}")
            raise

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the market module"""
        await self._close_websockets()
        
        if self._session:
            await self._session.close()
            self._session = None
        
        self._symbol_info_cache.clear()
        self._ticker_cache.clear()
        self._order_book_cache.clear()
        
        logger.info("BinanceMarket closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/binance/market", tags=["Binance Market"])


async def get_market(
    environment: BinanceEnvironment = Query(BinanceEnvironment.TESTNET)
) -> BinanceMarket:
    """Dependency to get BinanceMarket instance"""
    return BinanceMarket(environment=environment)


@router.get("/symbol/{symbol}")
async def get_symbol_info(
    symbol: str,
    market_type: BinanceMarketType = Query(BinanceMarketType.SPOT),
    market: BinanceMarket = Depends(get_market)
):
    """Get symbol information"""
    return await market.get_symbol_info(symbol, market_type)


@router.post("/data")
async def get_market_data(
    request: BinanceMarketDataRequest,
    market: BinanceMarket = Depends(get_market)
):
    """Get comprehensive market data"""
    return await market.get_market_data(request)


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    market_type: BinanceMarketType = Query(BinanceMarketType.SPOT),
    market: BinanceMarket = Depends(get_market)
):
    """Get ticker data"""
    return await market.get_ticker(symbol, market_type)


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    interval: BinanceKlineInterval = Query(BinanceKlineInterval.ONE_HOUR),
    limit: int = Query(500, le=1000),
    market_type: BinanceMarketType = Query(BinanceMarketType.SPOT),
    market: BinanceMarket = Depends(get_market)
):
    """Get candle data"""
    return await market.get_candles(symbol, interval, limit, market_type)


@router.get("/order-book/{symbol}")
async def get_order_book(
    symbol: str,
    market_type: BinanceMarketType = Query(BinanceMarketType.SPOT),
    limit: BinanceDepthLevel = Query(BinanceDepthLevel.LEVEL_10),
    market: BinanceMarket = Depends(get_market)
):
    """Get order book"""
    return await market.get_order_book(symbol, market_type, limit)


@router.get("/trades/{symbol}")
async def get_recent_trades(
    symbol: str,
    limit: int = Query(100, le=1000),
    market_type: BinanceMarketType = Query(BinanceMarketType.SPOT),
    market: BinanceMarket = Depends(get_market)
):
    """Get recent trades"""
    return await market.get_recent_trades(symbol, limit, market_type)


@router.get("/symbols")
async def get_all_symbols(
    market_type: BinanceMarketType = Query(BinanceMarketType.SPOT),
    market: BinanceMarket = Depends(get_market)
):
    """Get all symbols"""
    return await market.get_all_symbols(market_type)


@router.get("/export/{symbol}")
async def export_candles(
    symbol: str,
    interval: BinanceKlineInterval = Query(BinanceKlineInterval.ONE_HOUR),
    limit: int = Query(500, le=1000),
    market_type: BinanceMarketType = Query(BinanceMarketType.SPOT),
    market: BinanceMarket = Depends(get_market)
):
    """Export candles to CSV"""
    filename = await market.export_candles_to_csv(symbol, interval, limit, market_type)
    return FileResponse(filename, media_type='text/csv', filename=filename.split('/')[-1])


@router.websocket("/ws/{symbol}")
async def market_websocket(
    websocket: WebSocket,
    symbol: str,
    channels: List[str] = Query(...),
    interval: str = Query(None),
    depth: str = Query(None),
    market: BinanceMarket = Depends(get_market)
):
    """WebSocket endpoint for market data"""
    await websocket.accept()
    
    config = BinanceMarketStreamConfig(
        symbol=symbol,
        channels=channels,
        interval=interval,
        depth_level=depth
    )
    
    await market.subscribe(config, websocket)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await market.unsubscribe(f"{symbol}_{'_'.join(channels)}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BinanceMarket',
    'BinanceMarketType',
    'BinanceSymbolStatus',
    'BinanceKlineInterval',
    'BinanceSymbolInfo',
    'BinanceMarketDataRequest',
    'BinanceMarketDataResponse',
    'BinanceMarketStreamConfig',
    'router'
]
