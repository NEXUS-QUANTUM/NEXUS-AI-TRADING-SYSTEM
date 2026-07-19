"""
NEXUS AI TRADING SYSTEM - Coinbase Market Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/coinbase/market.py
Description: Coinbase market data with full API integration
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

# Coinbase imports
from trading.exchanges.coinbase.base import (
    CoinbaseBase,
    CoinbaseEnvironment,
    CoinbaseGranularity,
    CoinbaseCandle,
    CoinbaseTicker,
    CoinbaseOrderBook,
    CoinbaseTrade,
    CoinbaseProductInfo
)
from trading.exchanges.coinbase.exceptions import (
    CoinbaseException,
    CoinbaseMarketError,
    CoinbaseErrorCode,
    CoinbaseErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class CoinbaseMarketType(str, Enum):
    """Coinbase market types"""
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"


class CoinbaseProductStatus(str, Enum):
    """Coinbase product status"""
    ONLINE = "online"
    OFFLINE = "offline"
    HALTED = "halted"


class CoinbaseMarketDataRequest(BaseModel):
    """Request model for market data"""
    product_id: str
    market_type: CoinbaseMarketType = CoinbaseMarketType.SPOT
    granularity: CoinbaseGranularity = CoinbaseGranularity.ONE_HOUR
    limit: int = 500
    include_order_book: bool = True
    include_trades: bool = True
    include_ticker: bool = True


class CoinbaseMarketDataResponse(BaseModel):
    """Response model for market data"""
    product_id: str
    market_type: CoinbaseMarketType
    timestamp: datetime
    ticker: Optional[CoinbaseTicker] = None
    candles: List[CoinbaseCandle]
    order_book: Optional[CoinbaseOrderBook] = None
    trades: List[CoinbaseTrade]
    product_info: Optional[CoinbaseProductInfo] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CoinbaseMarketStreamConfig:
    """Coinbase market stream configuration"""
    product_ids: List[str]
    channels: List[str]
    granularity: Optional[str] = None


# =============================================================================
# COINBASE MARKET
# =============================================================================

class CoinbaseMarket:
    """
    Coinbase Market Data with full API integration.
    
    Features:
    - Real-time market data
    - Order book data
    - Trade data
    - Candle data
    - Ticker data
    - WebSocket streaming
    - Product information
    - Multiple market types
    """

    def __init__(
        self,
        config: Optional[ExchangeConfig] = None,
        environment: CoinbaseEnvironment = CoinbaseEnvironment.SANDBOX
    ):
        """
        Initialize CoinbaseMarket.
        
        Args:
            config: Exchange configuration
            environment: Coinbase environment
        """
        self.config = config or ExchangeConfig()
        self.environment = environment
        
        # Base URLs
        if environment == CoinbaseEnvironment.SANDBOX:
            self.base_url = "https://api-public.sandbox.exchange.coinbase.com"
            self.ws_url = "wss://ws-feed-public.sandbox.exchange.coinbase.com"
        else:
            self.base_url = "https://api.coinbase.com"
            self.ws_url = "wss://ws-feed.exchange.coinbase.com"
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # WebSocket manager
        self._ws_manager = WebSocketManager()
        self._ws_connections: Dict[str, WebSocket] = {}
        self._ws_subscriptions: Dict[str, List[str]] = {}
        
        # Cache
        self._product_cache: Dict[str, CoinbaseProductInfo] = {}
        self._ticker_cache: Dict[str, CoinbaseTicker] = {}
        self._order_book_cache: Dict[str, CoinbaseOrderBook] = {}
        
        # Error handler
        self._error_handler = CoinbaseErrorHandler()
        
        # Stream handlers
        self._stream_handlers: Dict[str, List] = {}
        
        logger.info(f"CoinbaseMarket initialized in {environment.value}")

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
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an API request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            Dict[str, Any]: Response data
        """
        try:
            url = f"{self.base_url}{endpoint}"
            
            async with self._session.request(
                method=method,
                url=url,
                params=params
            ) as response:
                data = await response.json()
                
                if response.status >= 400:
                    error_msg = data.get('message', 'Unknown error')
                    raise CoinbaseMarketError(
                        code=CoinbaseErrorCode.UNKNOWN,
                        message=f"Market data request failed: {error_msg}"
                    )
                
                return data
                
        except CoinbaseException:
            raise
        except Exception as e:
            logger.error(f"API request error: {e}")
            raise CoinbaseMarketError(
                code=CoinbaseErrorCode.UNKNOWN,
                message=f"Market data request failed: {str(e)}"
            )

    # =========================================================================
    # Product Information
    # =========================================================================

    async def get_product_info(
        self,
        product_id: str
    ) -> CoinbaseProductInfo:
        """
        Get product information.
        
        Args:
            product_id: Product ID
            
        Returns:
            CoinbaseProductInfo: Product information
        """
        try:
            # Check cache
            if product_id in self._product_cache:
                return self._product_cache[product_id]
            
            response = await self._request(
                method='GET',
                endpoint=f'/api/v3/brokerage/products/{product_id}'
            )
            
            data = response
            
            product_info = CoinbaseProductInfo(
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
            
            # Cache
            self._product_cache[product_id] = product_info
            
            return product_info
            
        except Exception as e:
            logger.error(f"Error getting product info: {e}")
            raise

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_market_data(
        self,
        request: CoinbaseMarketDataRequest
    ) -> CoinbaseMarketDataResponse:
        """
        Get comprehensive market data.
        
        Args:
            request: Market data request
            
        Returns:
            CoinbaseMarketDataResponse: Market data
        """
        try:
            # Get product info
            product_info = await self.get_product_info(request.product_id)
            
            # Get ticker
            ticker = None
            if request.include_ticker:
                ticker = await self.get_ticker(request.product_id)
            
            # Get candles
            candles = await self.get_candles(
                request.product_id,
                request.granularity,
                request.limit
            )
            
            # Get order book
            order_book = None
            if request.include_order_book:
                order_book = await self.get_order_book(request.product_id)
            
            # Get trades
            trades = []
            if request.include_trades:
                trades = await self.get_recent_trades(
                    request.product_id,
                    limit=100
                )
            
            return CoinbaseMarketDataResponse(
                product_id=request.product_id,
                market_type=request.market_type,
                timestamp=datetime.utcnow(),
                ticker=ticker,
                candles=candles,
                order_book=order_book,
                trades=trades,
                product_info=product_info
            )
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            raise

    # =========================================================================
    # Ticker
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
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
                endpoint=f'/api/v3/brokerage/products/{product_id}/ticker'
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

    # =========================================================================
    # Candles
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
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
                params=params
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

    # =========================================================================
    # Order Book
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
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
                params={'level': level}
            )
            
            data = response
            
            from trading.exchanges.coinbase.base import CoinbaseOrderBookLevel
            
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

    # =========================================================================
    # Trades
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
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
                params={'limit': limit}
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

    # =========================================================================
    # All Products
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_all_products(self) -> List[str]:
        """
        Get all product IDs.
        
        Returns:
            List[str]: List of product IDs
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/api/v3/brokerage/products'
            )
            
            products = []
            for data in response.get('products', []):
                if not data.get('trading_disabled', False):
                    products.append(data.get('product_id'))
            
            return products
            
        except Exception as e:
            logger.error(f"Error getting all products: {e}")
            raise

    # =========================================================================
    # WebSocket Streaming
    # =========================================================================

    async def subscribe(
        self,
        config: CoinbaseMarketStreamConfig,
        websocket: WebSocket
    ) -> None:
        """
        Subscribe to market streams.
        
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
            
            # Connect to WebSocket
            ws = await websockets.connect(self.ws_url)
            
            self._ws_connections[stream_key] = ws
            self._ws_subscriptions[stream_key] = config.channels
            
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
        product_id: str,
        granularity: CoinbaseGranularity,
        limit: int = 500,
        filename: Optional[str] = None
    ) -> str:
        """
        Export candles to CSV.
        
        Args:
            product_id: Product ID
            granularity: Candle granularity
            limit: Number of candles
            filename: Output filename
            
        Returns:
            str: Filename
        """
        try:
            candles = await self.get_candles(product_id, granularity, limit)
            
            data = []
            for c in candles:
                data.append({
                    'timestamp': c.timestamp.isoformat(),
                    'open': c.open,
                    'high': c.high,
                    'low': c.low,
                    'close': c.close,
                    'volume': c.volume
                })
            
            df = pd.DataFrame(data)
            
            if not filename:
                filename = f"{product_id}_{granularity.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            
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
        
        self._product_cache.clear()
        self._ticker_cache.clear()
        self._order_book_cache.clear()
        
        logger.info("CoinbaseMarket closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/v1/exchanges/coinbase/market", tags=["Coinbase Market"])


async def get_market(
    environment: CoinbaseEnvironment = Query(CoinbaseEnvironment.SANDBOX)
) -> CoinbaseMarket:
    """Dependency to get CoinbaseMarket instance"""
    return CoinbaseMarket(environment=environment)


@router.get("/product/{product_id}")
async def get_product_info(
    product_id: str,
    market: CoinbaseMarket = Depends(get_market)
):
    """Get product information"""
    return await market.get_product_info(product_id)


@router.post("/data")
async def get_market_data(
    request: CoinbaseMarketDataRequest,
    market: CoinbaseMarket = Depends(get_market)
):
    """Get comprehensive market data"""
    return await market.get_market_data(request)


@router.get("/ticker/{product_id}")
async def get_ticker(
    product_id: str,
    market: CoinbaseMarket = Depends(get_market)
):
    """Get ticker data"""
    return await market.get_ticker(product_id)


@router.get("/candles/{product_id}")
async def get_candles(
    product_id: str,
    granularity: CoinbaseGranularity = Query(CoinbaseGranularity.ONE_HOUR),
    limit: int = Query(500, le=1000),
    market: CoinbaseMarket = Depends(get_market)
):
    """Get candle data"""
    return await market.get_candles(product_id, granularity, limit)


@router.get("/order-book/{product_id}")
async def get_order_book(
    product_id: str,
    level: int = Query(2, ge=1, le=3),
    market: CoinbaseMarket = Depends(get_market)
):
    """Get order book"""
    return await market.get_order_book(product_id, level)


@router.get("/trades/{product_id}")
async def get_recent_trades(
    product_id: str,
    limit: int = Query(100, le=1000),
    market: CoinbaseMarket = Depends(get_market)
):
    """Get recent trades"""
    return await market.get_recent_trades(product_id, limit)


@router.get("/products")
async def get_all_products(
    market: CoinbaseMarket = Depends(get_market)
):
    """Get all products"""
    return await market.get_all_products()


@router.get("/export/{product_id}")
async def export_candles(
    product_id: str,
    granularity: CoinbaseGranularity = Query(CoinbaseGranularity.ONE_HOUR),
    limit: int = Query(500, le=1000),
    market: CoinbaseMarket = Depends(get_market)
):
    """Export candles to CSV"""
    filename = await market.export_candles_to_csv(product_id, granularity, limit)
    return FileResponse(filename, media_type='text/csv', filename=filename.split('/')[-1])


@router.websocket("/ws/{product_id}")
async def market_websocket(
    websocket: WebSocket,
    product_id: str,
    channels: List[str] = Query(...),
    market: CoinbaseMarket = Depends(get_market)
):
    """WebSocket endpoint for market data"""
    await websocket.accept()
    
    config = CoinbaseMarketStreamConfig(
        product_ids=[product_id],
        channels=channels
    )
    
    await market.subscribe(config, websocket)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await market.unsubscribe(f"{product_id}_{'_'.join(channels)}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CoinbaseMarket',
    'CoinbaseMarketType',
    'CoinbaseProductStatus',
    'CoinbaseMarketDataRequest',
    'CoinbaseMarketDataResponse',
    'CoinbaseMarketStreamConfig',
    'router'
]
