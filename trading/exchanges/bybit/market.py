"""
NEXUS AI TRADING SYSTEM - Bybit Market Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/market.py
Description: Bybit market data with full API integration
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

# Bybit imports
from trading.exchanges.bybit.base import (
    BybitBase,
    BybitEnvironment,
    BybitInterval,
    BybitDepthLevel,
    BybitCategory,
    BybitCandle,
    BybitTicker,
    BybitOrderBook,
    BybitTrade,
    BybitInstrumentInfo
)
from trading.exchanges.bybit.exceptions import (
    BybitException,
    BybitMarketError,
    BybitErrorCode,
    BybitErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BybitMarketType(str, Enum):
    """Bybit market types"""
    SPOT = "spot"
    LINEAR = "linear"
    INVERSE = "inverse"
    OPTION = "option"


class BybitSymbolStatus(str, Enum):
    """Bybit symbol status"""
    TRADING = "Trading"
    BREAK = "Break"
    HALT = "Halt"
    CLOSED = "Closed"


class BybitKlineInterval(str, Enum):
    """Bybit kline intervals"""
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


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BybitSymbolInfo(BaseModel):
    """Bybit symbol information"""
    symbol: str
    status: BybitSymbolStatus
    base_currency: str
    quote_currency: str
    contract_type: str
    min_order_qty: float
    max_order_qty: float
    qty_step: float
    min_price: float
    max_price: float
    price_step: float
    leverage: int
    margin_mode: str


class BybitMarketDataRequest(BaseModel):
    """Request model for market data"""
    symbol: str
    market_type: BybitMarketType = BybitMarketType.LINEAR
    interval: BybitKlineInterval = BybitKlineInterval.ONE_HOUR
    limit: int = 500
    include_order_book: bool = True
    include_trades: bool = True
    include_ticker: bool = True


class BybitMarketDataResponse(BaseModel):
    """Response model for market data"""
    symbol: str
    market_type: BybitMarketType
    timestamp: datetime
    ticker: Optional[BybitTicker] = None
    candles: List[BybitCandle]
    order_book: Optional[BybitOrderBook] = None
    trades: List[BybitTrade]
    symbol_info: Optional[BybitSymbolInfo] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BybitMarketStreamConfig:
    """Bybit market stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BYBIT MARKET
# =============================================================================

class BybitMarket:
    """
    Bybit Market Data with full API integration.
    
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
        environment: BybitEnvironment = BybitEnvironment.TESTNET
    ):
        """
        Initialize BybitMarket.
        
        Args:
            config: Exchange configuration
            environment: Bybit environment
        """
        self.config = config or ExchangeConfig()
        self.environment = environment
        
        # Base URLs
        if environment == BybitEnvironment.TESTNET:
            self.base_url = "https://api-testnet.bybit.com"
            self.ws_url = "wss://stream-testnet.bybit.com/v5/public/linear"
        else:
            self.base_url = "https://api.bybit.com"
            self.ws_url = "wss://stream.bybit.com/v5/public/linear"
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # WebSocket manager
        self._ws_manager = WebSocketManager()
        self._ws_connections: Dict[str, WebSocket] = {}
        self._ws_subscriptions: Dict[str, List[str]] = {}
        
        # Cache
        self._symbol_info_cache: Dict[str, BybitSymbolInfo] = {}
        self._ticker_cache: Dict[str, BybitTicker] = {}
        self._order_book_cache: Dict[str, BybitOrderBook] = {}
        
        # Error handler
        self._error_handler = BybitErrorHandler()
        
        # Stream handlers
        self._stream_handlers: Dict[str, List] = {}
        
        logger.info(f"BybitMarket initialized in {environment.value}")

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
        market_type: BybitMarketType = BybitMarketType.LINEAR
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
            # Determine category
            category_map = {
                BybitMarketType.SPOT: 'spot',
                BybitMarketType.LINEAR: 'linear',
                BybitMarketType.INVERSE: 'inverse',
                BybitMarketType.OPTION: 'option'
            }
            category = category_map.get(market_type, 'linear')
            
            # Add category to params
            if params is None:
                params = {}
            params['category'] = category
            
            url = f"{self.base_url}{endpoint}"
            
            async with self._session.request(
                method=method,
                url=url,
                params=params
            ) as response:
                data = await response.json()
                
                if response.status >= 400:
                    error_msg = data.get('retMsg', 'Unknown error')
                    error_code = data.get('retCode', -1)
                    raise BybitException(
                        code=BybitErrorCode(error_code) if error_code in BybitErrorCode.__members__ else BybitErrorCode.UNKNOWN,
                        message=error_msg,
                        data={'status': response.status, 'response': data}
                    )
                
                if data.get('retCode') != 0:
                    raise BybitException(
                        code=BybitErrorCode(data.get('retCode')) if data.get('retCode') in BybitErrorCode.__members__ else BybitErrorCode.UNKNOWN,
                        message=data.get('retMsg', 'Unknown error'),
                        data={'response': data}
                    )
                
                return data.get('result', {})
                
        except BybitException:
            raise
        except Exception as e:
            logger.error(f"API request error: {e}")
            raise BybitMarketError(
                code=BybitErrorCode.UNKNOWN,
                message=f"Market data request failed: {str(e)}"
            )

    # =========================================================================
    # Symbol Information
    # =========================================================================

    async def get_symbol_info(
        self,
        symbol: str,
        market_type: BybitMarketType = BybitMarketType.LINEAR
    ) -> BybitSymbolInfo:
        """
        Get symbol information.
        
        Args:
            symbol: Symbol
            market_type: Market type
            
        Returns:
            BybitSymbolInfo: Symbol information
        """
        try:
            # Check cache
            cache_key = f"{market_type.value}_{symbol}"
            if cache_key in self._symbol_info_cache:
                return self._symbol_info_cache[cache_key]
            
            # Get instruments
            params = {'symbol': symbol}
            response = await self._request(
                method='GET',
                endpoint='/v5/market/instruments-info',
                params=params,
                market_type=market_type
            )
            
            if not response.get('list'):
                raise BybitMarketError(
                    code=BybitErrorCode.INVALID_SYMBOL,
                    message=f"Symbol {symbol} not found"
                )
            
            data = response['list'][0]
            
            symbol_info = BybitSymbolInfo(
                symbol=data['symbol'],
                status=BybitSymbolStatus(data.get('status', 'Trading')),
                base_currency=data.get('baseCoin', ''),
                quote_currency=data.get('quoteCoin', ''),
                contract_type=data.get('contractType', ''),
                min_order_qty=float(data.get('lotSizeFilter', {}).get('minOrderQty', 0)),
                max_order_qty=float(data.get('lotSizeFilter', {}).get('maxOrderQty', 0)),
                qty_step=float(data.get('lotSizeFilter', {}).get('qtyStep', 0)),
                min_price=float(data.get('priceFilter', {}).get('minPrice', 0)),
                max_price=float(data.get('priceFilter', {}).get('maxPrice', 0)),
                price_step=float(data.get('priceFilter', {}).get('tickSize', 0)),
                leverage=int(data.get('leverageFilter', {}).get('maxLeverage', 1)),
                margin_mode=data.get('marginMode', 'ISOLATED')
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
        request: BybitMarketDataRequest
    ) -> BybitMarketDataResponse:
        """
        Get comprehensive market data.
        
        Args:
            request: Market data request
            
        Returns:
            BybitMarketDataResponse: Market data
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
            
            return BybitMarketDataResponse(
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
        market_type: BybitMarketType = BybitMarketType.LINEAR
    ) -> BybitTicker:
        """
        Get ticker for symbol.
        
        Args:
            symbol: Symbol
            market_type: Market type
            
        Returns:
            BybitTicker: Ticker data
        """
        try:
            # Check cache
            cache_key = f"{market_type.value}_{symbol}"
            if cache_key in self._ticker_cache:
                cached = self._ticker_cache[cache_key]
                if (datetime.utcnow() - cached.timestamp).seconds < 5:
                    return cached
            
            params = {'symbol': symbol}
            response = await self._request(
                method='GET',
                endpoint='/v5/market/tickers',
                params=params,
                market_type=market_type
            )
            
            if not response.get('list'):
                raise BybitMarketError(
                    code=BybitErrorCode.INVALID_SYMBOL,
                    message=f"No ticker data for {symbol}"
                )
            
            data = response['list'][0]
            
            ticker = BybitTicker(
                symbol=data['symbol'],
                price=float(data['lastPrice']),
                price_change=float(data.get('price24hPcnt', 0)) * float(data['lastPrice']),
                price_change_pct=float(data.get('price24hPcnt', 0)) * 100,
                volume=float(data.get('volume24h', 0)),
                turnover=float(data.get('turnover24h', 0)),
                high=float(data.get('highPrice24h', 0)),
                low=float(data.get('lowPrice24h', 0)),
                open=float(data.get('openPrice24h', 0)),
                close=float(data['lastPrice']),
                bid=float(data.get('bid1Price', 0)),
                ask=float(data.get('ask1Price', 0)),
                bid_size=float(data.get('bid1Size', 0)),
                ask_size=float(data.get('ask1Size', 0)),
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
        interval: BybitKlineInterval = BybitKlineInterval.ONE_HOUR,
        limit: int = 500,
        market_type: BybitMarketType = BybitMarketType.LINEAR
    ) -> List[BybitCandle]:
        """
        Get candle data.
        
        Args:
            symbol: Symbol
            interval: Candle interval
            limit: Number of candles
            market_type: Market type
            
        Returns:
            List[BybitCandle]: Candle data
        """
        try:
            params = {
                'symbol': symbol,
                'interval': interval.value,
                'limit': limit
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/kline',
                params=params,
                market_type=market_type
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

    # =========================================================================
    # Order Book
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order_book(
        self,
        symbol: str,
        market_type: BybitMarketType = BybitMarketType.LINEAR,
        limit: BybitDepthLevel = BybitDepthLevel.LEVEL_10
    ) -> BybitOrderBook:
        """
        Get order book.
        
        Args:
            symbol: Symbol
            market_type: Market type
            limit: Depth level
            
        Returns:
            BybitOrderBook: Order book data
        """
        try:
            # Check cache
            cache_key = f"{market_type.value}_{symbol}"
            if cache_key in self._order_book_cache:
                cached = self._order_book_cache[cache_key]
                if (datetime.utcnow() - cached.timestamp).seconds < 5:
                    return cached
            
            params = {
                'symbol': symbol,
                'limit': limit.value
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/orderbook',
                params=params,
                market_type=market_type
            )
            
            from trading.exchanges.bybit.base import BybitOrderBookLevel
            
            bids = [BybitOrderBookLevel(price=float(b[0]), size=float(b[1])) for b in response.get('b', [])]
            asks = [BybitOrderBookLevel(price=float(a[0]), size=float(a[1])) for a in response.get('a', [])]
            
            order_book = BybitOrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=datetime.utcnow(),
                update_id=int(response.get('u', 0))
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
        market_type: BybitMarketType = BybitMarketType.LINEAR
    ) -> List[BybitTrade]:
        """
        Get recent trades.
        
        Args:
            symbol: Symbol
            limit: Number of trades
            market_type: Market type
            
        Returns:
            List[BybitTrade]: Trade data
        """
        try:
            params = {
                'symbol': symbol,
                'limit': limit
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/recent-trade',
                params=params,
                market_type=market_type
            )
            
            trades = []
            for data in response.get('list', []):
                trades.append(BybitTrade(
                    symbol=data['symbol'],
                    price=float(data['price']),
                    quantity=float(data['size']),
                    trade_time=datetime.fromtimestamp(int(data['time']) / 1000),
                    side=data.get('side', '').lower(),
                    trade_id=data['tradeId']
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
        market_type: BybitMarketType = BybitMarketType.LINEAR
    ) -> List[str]:
        """
        Get all symbols.
        
        Args:
            market_type: Market type
            
        Returns:
            List[str]: List of symbols
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/v5/market/instruments-info',
                market_type=market_type
            )
            
            symbols = []
            for data in response.get('list', []):
                if data.get('status') == 'Trading':
                    symbols.append(data.get('symbol'))
            
            return symbols
            
        except Exception as e:
            logger.error(f"Error getting all symbols: {e}")
            raise

    # =========================================================================
    # WebSocket Streaming
    # =========================================================================

    async def subscribe(
        self,
        config: BybitMarketStreamConfig,
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
            
            # Build subscription args
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
            ws_url = f"{self.ws_url}"
            ws = await websockets.connect(ws_url)
            
            self._ws_connections[stream_key] = ws
            self._ws_subscriptions[stream_key] = config.channels
            
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
        interval: BybitKlineInterval,
        limit: int = 500,
        market_type: BybitMarketType = BybitMarketType.LINEAR,
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
                    'turnover': c.turnover
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
        
        logger.info("BybitMarket closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/bybit/market", tags=["Bybit Market"])


async def get_market(
    environment: BybitEnvironment = Query(BybitEnvironment.TESTNET)
) -> BybitMarket:
    """Dependency to get BybitMarket instance"""
    return BybitMarket(environment=environment)


@router.get("/symbol/{symbol}")
async def get_symbol_info(
    symbol: str,
    market_type: BybitMarketType = Query(BybitMarketType.LINEAR),
    market: BybitMarket = Depends(get_market)
):
    """Get symbol information"""
    return await market.get_symbol_info(symbol, market_type)


@router.post("/data")
async def get_market_data(
    request: BybitMarketDataRequest,
    market: BybitMarket = Depends(get_market)
):
    """Get comprehensive market data"""
    return await market.get_market_data(request)


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    market_type: BybitMarketType = Query(BybitMarketType.LINEAR),
    market: BybitMarket = Depends(get_market)
):
    """Get ticker data"""
    return await market.get_ticker(symbol, market_type)


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    interval: BybitKlineInterval = Query(BybitKlineInterval.ONE_HOUR),
    limit: int = Query(500, le=1000),
    market_type: BybitMarketType = Query(BybitMarketType.LINEAR),
    market: BybitMarket = Depends(get_market)
):
    """Get candle data"""
    return await market.get_candles(symbol, interval, limit, market_type)


@router.get("/order-book/{symbol}")
async def get_order_book(
    symbol: str,
    market_type: BybitMarketType = Query(BybitMarketType.LINEAR),
    limit: BybitDepthLevel = Query(BybitDepthLevel.LEVEL_10),
    market: BybitMarket = Depends(get_market)
):
    """Get order book"""
    return await market.get_order_book(symbol, market_type, limit)


@router.get("/trades/{symbol}")
async def get_recent_trades(
    symbol: str,
    limit: int = Query(100, le=1000),
    market_type: BybitMarketType = Query(BybitMarketType.LINEAR),
    market: BybitMarket = Depends(get_market)
):
    """Get recent trades"""
    return await market.get_recent_trades(symbol, limit, market_type)


@router.get("/symbols")
async def get_all_symbols(
    market_type: BybitMarketType = Query(BybitMarketType.LINEAR),
    market: BybitMarket = Depends(get_market)
):
    """Get all symbols"""
    return await market.get_all_symbols(market_type)


@router.get("/export/{symbol}")
async def export_candles(
    symbol: str,
    interval: BybitKlineInterval = Query(BybitKlineInterval.ONE_HOUR),
    limit: int = Query(500, le=1000),
    market_type: BybitMarketType = Query(BybitMarketType.LINEAR),
    market: BybitMarket = Depends(get_market)
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
    market: BybitMarket = Depends(get_market)
):
    """WebSocket endpoint for market data"""
    await websocket.accept()
    
    config = BybitMarketStreamConfig(
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
    'BybitMarket',
    'BybitMarketType',
    'BybitSymbolStatus',
    'BybitKlineInterval',
    'BybitSymbolInfo',
    'BybitMarketDataRequest',
    'BybitMarketDataResponse',
    'BybitMarketStreamConfig',
    'router'
]
