"""
NEXUS AI TRADING SYSTEM - Forex Base Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/forex/base.py
Description: Forex exchange base classes and utilities with full API integration
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

class ForexProvider(str, Enum):
    """Forex data providers"""
    OANDA = "oanda"
    FXCM = "fxcm"
    DUKASCOPY = "dukascopy"
    FOREXCOM = "forexcom"
    IG = "ig"
    PEPPERSTONE = "pepperstone"


class ForexEnvironment(str, Enum):
    """Forex environment"""
    PRODUCTION = "production"
    DEMO = "demo"
    PRACTICE = "practice"


class ForexInstrumentType(str, Enum):
    """Forex instrument types"""
    CURRENCY = "currency"
    METAL = "metal"
    COMMODITY = "commodity"
    INDEX = "index"
    CFD = "cfd"


class ForexGranularity(str, Enum):
    """Forex candle granularities"""
    S5 = "S5"  # 5 seconds
    S10 = "S10"  # 10 seconds
    S15 = "S15"  # 15 seconds
    S30 = "S30"  # 30 seconds
    M1 = "M1"  # 1 minute
    M2 = "M2"  # 2 minutes
    M3 = "M3"  # 3 minutes
    M4 = "M4"  # 4 minutes
    M5 = "M5"  # 5 minutes
    M10 = "M10"  # 10 minutes
    M15 = "M15"  # 15 minutes
    M30 = "M30"  # 30 minutes
    H1 = "H1"  # 1 hour
    H2 = "H2"  # 2 hours
    H3 = "H3"  # 3 hours
    H4 = "H4"  # 4 hours
    H6 = "H6"  # 6 hours
    H8 = "H8"  # 8 hours
    H12 = "H12"  # 12 hours
    D = "D"  # 1 day
    W = "W"  # 1 week
    M = "M"  # 1 month


class ForexOrderType(str, Enum):
    """Forex order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TAKEPROFIT = "take_profit"
    STOPLOSS = "stop_loss"


class ForexOrderSide(str, Enum):
    """Forex order sides"""
    BUY = "buy"
    SELL = "sell"


class ForexTimeInForce(str, Enum):
    """Forex time in force"""
    GTC = "gtc"  # Good till cancelled
    DAY = "day"  # Good for day
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ForexInstrument(BaseModel):
    """Forex instrument"""
    name: str
    display_name: str
    instrument_type: ForexInstrumentType
    pip_location: int
    pip_size: float
    tradeable: bool
    min_trade_size: float
    max_trade_size: float
    step_size: float
    quote_currency: str


class ForexPrice(BaseModel):
    """Forex price"""
    instrument: str
    bid: float
    ask: float
    spread: float
    timestamp: datetime


class ForexCandle(BaseModel):
    """Forex candle"""
    instrument: str
    granularity: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    complete: bool


class ForexOrderBook(BaseModel):
    """Forex order book"""
    instrument: str
    bids: List[Dict[str, float]]
    asks: List[Dict[str, float]]
    timestamp: datetime


class ForexPosition(BaseModel):
    """Forex position"""
    instrument: str
    units: float
    average_price: float
    unrealized_pnl: float
    realized_pnl: float
    side: str
    timestamp: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ForexCredentials:
    """Forex API credentials"""
    api_key: str
    account_id: str
    provider: ForexProvider = ForexProvider.OANDA


@dataclass
class ForexApiLimits:
    """Forex API limits"""
    requests_per_second: int = 10
    orders_per_second: int = 5
    websocket_connections: int = 5


@dataclass
class ForexWebSocketMessage:
    """Forex WebSocket message"""
    type: str
    data: Dict[str, Any]
    timestamp: datetime


# =============================================================================
# FOREX BASE CLASS
# =============================================================================

class ForexBase:
    """
    Forex Exchange Base Class with full API integration.
    
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

    def __init__(
        self,
        credentials: ForexCredentials,
        environment: ForexEnvironment = ForexEnvironment.PRACTICE,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize ForexBase.
        
        Args:
            credentials: Forex API credentials
            environment: Forex environment
            config: Exchange configuration
        """
        self.credentials = credentials
        self.environment = environment
        self.config = config or ExchangeConfig()
        
        # Base URLs
        self.base_url = self._get_base_url()
        self.ws_url = self._get_ws_url()
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        
        # Rate limiting
        self._rate_limits = ForexApiLimits()
        self._request_timestamps: List[float] = []
        self._order_timestamps: List[float] = []
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Instrument info
        self._instrument_info: Dict[str, ForexInstrument] = {}
        
        # Cache
        self._price_cache: Dict[str, ForexPrice] = {}
        self._candle_cache: Dict[str, List[ForexCandle]] = {}
        
        # Stream handlers
        self._stream_handlers: Dict[str, List] = {}
        
        logger.info(f"ForexBase initialized for {credentials.provider.value}")

    def _get_base_url(self) -> str:
        """Get base URL based on provider and environment"""
        provider_urls = {
            ForexProvider.OANDA: {
                ForexEnvironment.PRODUCTION: "https://api-fxtrade.oanda.com",
                ForexEnvironment.DEMO: "https://api-fxpractice.oanda.com",
                ForexEnvironment.PRACTICE: "https://api-fxpractice.oanda.com"
            },
            ForexProvider.FXCM: {
                ForexEnvironment.PRODUCTION: "https://api.fxcm.com",
                ForexEnvironment.DEMO: "https://api-demo.fxcm.com",
                ForexEnvironment.PRACTICE: "https://api-demo.fxcm.com"
            }
        }
        
        return provider_urls.get(self.credentials.provider, {}).get(
            self.environment,
            "https://api-fxpractice.oanda.com"
        )

    def _get_ws_url(self) -> str:
        """Get WebSocket URL based on provider and environment"""
        provider_ws_urls = {
            ForexProvider.OANDA: {
                ForexEnvironment.PRODUCTION: "wss://stream-fxtrade.oanda.com",
                ForexEnvironment.DEMO: "wss://stream-fxpractice.oanda.com",
                ForexEnvironment.PRACTICE: "wss://stream-fxpractice.oanda.com"
            }
        }
        
        return provider_ws_urls.get(self.credentials.provider, {}).get(
            self.environment,
            "wss://stream-fxpractice.oanda.com"
        )

    # =========================================================================
    # Session Management
    # =========================================================================

    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession(
            headers={
                'Authorization': f'Bearer {self.credentials.api_key}',
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

    @retry_async(max_attempts=3, delay=0.5, backoff=2.0)
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an API request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request data
            
        Returns:
            Dict[str, Any]: Response data
        """
        try:
            # Check rate limits
            await self._check_rate_limits()
            
            # Prepare request
            url = f"{self.base_url}{endpoint}"
            
            # Make request
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=data
            ) as response:
                # Update rate limits
                self._update_rate_limits()
                
                # Parse response
                response_data = await response.json()
                
                if response.status >= 400:
                    error_msg = response_data.get('message', 'Unknown error')
                    raise Exception(f"Forex API error: {error_msg}")
                
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

    # =========================================================================
    # Account Information
    # =========================================================================

    async def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Dict[str, Any]: Account information
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/v3/accounts/' + self.credentials.account_id
            )
            
            return response.get('account', {})
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            raise

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_instruments(self) -> List[ForexInstrument]:
        """
        Get available instruments.
        
        Returns:
            List[ForexInstrument]: Instruments
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/v3/accounts/' + self.credentials.account_id + '/instruments'
            )
            
            instruments = []
            for data in response.get('instruments', []):
                instrument = ForexInstrument(
                    name=data.get('name'),
                    display_name=data.get('displayName'),
                    instrument_type=ForexInstrumentType(data.get('type', 'currency')),
                    pip_location=data.get('pipLocation', 4),
                    pip_size=data.get('pipSize', 0.0001),
                    tradeable=data.get('tradeable', True),
                    min_trade_size=float(data.get('minimumTradeSize', 1)),
                    max_trade_size=float(data.get('maximumTradeSize', 10000000)),
                    step_size=float(data.get('stepSize', 1)),
                    quote_currency=data.get('quoteCurrency', 'USD')
                )
                instruments.append(instrument)
                self._instrument_info[instrument.name] = instrument
            
            return instruments
            
        except Exception as e:
            logger.error(f"Error getting instruments: {e}")
            raise

    async def get_price(self, instrument: str) -> ForexPrice:
        """
        Get current price for instrument.
        
        Args:
            instrument: Instrument name
            
        Returns:
            ForexPrice: Price data
        """
        try:
            # Check cache
            if instrument in self._price_cache:
                cached = self._price_cache[instrument]
                if (datetime.utcnow() - cached.timestamp).seconds < 5:
                    return cached
            
            params = {'instruments': instrument}
            response = await self._request(
                method='GET',
                endpoint='/v3/accounts/' + self.credentials.account_id + '/pricing',
                params=params
            )
            
            data = response.get('prices', [])[0]
            
            price = ForexPrice(
                instrument=data.get('instrument'),
                bid=float(data.get('bids', [{'price': 0}])[0].get('price', 0)),
                ask=float(data.get('asks', [{'price': 0}])[0].get('price', 0)),
                spread=float(data.get('bids', [{'price': 0}])[0].get('price', 0)) - float(data.get('asks', [{'price': 0}])[0].get('price', 0)),
                timestamp=datetime.utcnow()
            )
            
            # Cache
            self._price_cache[instrument] = price
            
            return price
            
        except Exception as e:
            logger.error(f"Error getting price for {instrument}: {e}")
            raise

    async def get_candles(
        self,
        instrument: str,
        granularity: ForexGranularity = ForexGranularity.H1,
        count: int = 500
    ) -> List[ForexCandle]:
        """
        Get candle data.
        
        Args:
            instrument: Instrument name
            granularity: Candle granularity
            count: Number of candles
            
        Returns:
            List[ForexCandle]: Candle data
        """
        try:
            params = {
                'granularity': granularity.value,
                'count': count
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v3/instruments/' + instrument + '/candles',
                params=params
            )
            
            candles = []
            for data in response.get('candles', []):
                mid = data.get('mid', {})
                candles.append(ForexCandle(
                    instrument=instrument,
                    granularity=granularity.value,
                    timestamp=datetime.utcnow(),
                    open=float(mid.get('o', 0)),
                    high=float(mid.get('h', 0)),
                    low=float(mid.get('l', 0)),
                    close=float(mid.get('c', 0)),
                    volume=int(data.get('volume', 0)),
                    complete=data.get('complete', True)
                ))
            
            # Cache
            self._candle_cache[instrument] = candles
            
            return candles
            
        except Exception as e:
            logger.error(f"Error getting candles for {instrument}: {e}")
            raise

    # =========================================================================
    # Order Management
    # =========================================================================

    async def place_order(
        self,
        instrument: str,
        side: ForexOrderSide,
        units: float,
        order_type: ForexOrderType = ForexOrderType.MARKET,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        time_in_force: ForexTimeInForce = ForexTimeInForce.GTC
    ) -> Dict[str, Any]:
        """
        Place an order.
        
        Args:
            instrument: Instrument name
            side: Order side
            units: Order units
            order_type: Order type
            price: Limit price
            stop_loss: Stop loss price
            take_profit: Take profit price
            time_in_force: Time in force
            
        Returns:
            Dict[str, Any]: Order response
        """
        try:
            data = {
                'order': {
                    'instrument': instrument,
                    'units': str(units),
                    'type': order_type.value.upper(),
                    'timeInForce': time_in_force.value.upper()
                }
            }
            
            if side == ForexOrderSide.BUY:
                data['order']['positionFill'] = 'DEFAULT'
            
            if price:
                data['order']['price'] = str(price)
            
            if stop_loss:
                data['order']['stopLossOnFill'] = {'price': str(stop_loss)}
            
            if take_profit:
                data['order']['takeProfitOnFill'] = {'price': str(take_profit)}
            
            response = await self._request(
                method='POST',
                endpoint='/v3/accounts/' + self.credentials.account_id + '/orders',
                data=data
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    # =========================================================================
    # Position Management
    # =========================================================================

    async def get_positions(self) -> List[ForexPosition]:
        """
        Get open positions.
        
        Returns:
            List[ForexPosition]: Positions
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/v3/accounts/' + self.credentials.account_id + '/positions'
            )
            
            positions = []
            for data in response.get('positions', []):
                position = ForexPosition(
                    instrument=data.get('instrument'),
                    units=float(data.get('long', {}).get('units', 0)) or float(data.get('short', {}).get('units', 0)),
                    average_price=float(data.get('long', {}).get('averagePrice', 0)) or float(data.get('short', {}).get('averagePrice', 0)),
                    unrealized_pnl=float(data.get('long', {}).get('unrealizedPL', 0)) or float(data.get('short', {}).get('unrealizedPL', 0)),
                    realized_pnl=float(data.get('long', {}).get('realizedPL', 0)) or float(data.get('short', {}).get('realizedPL', 0)),
                    side='long' if float(data.get('long', {}).get('units', 0)) > 0 else 'short',
                    timestamp=datetime.utcnow()
                )
                positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            raise

    # =========================================================================
    # WebSocket Management
    # =========================================================================

    async def subscribe_prices(self, instruments: List[str]) -> None:
        """
        Subscribe to price streams.
        
        Args:
            instruments: List of instruments
        """
        try:
            # Build stream key
            stream_key = f"prices_{'_'.join(instruments)}"
            
            # Connect to WebSocket
            ws_url = f"{self.ws_url}/v3/accounts/{self.credentials.account_id}/pricing/stream"
            ws = await websockets.connect(
                ws_url,
                extra_headers={'Authorization': f'Bearer {self.credentials.api_key}'}
            )
            
            self._ws_connections[stream_key] = ws
            
            # Send subscription
            subscribe_msg = {
                "type": "subscribe",
                "instruments": instruments
            }
            await ws.send(json.dumps(subscribe_msg))
            
            # Start receiving messages
            asyncio.create_task(self._receive_ws_messages(stream_key))
            
            logger.info(f"Subscribed to prices for {instruments}")
            
        except Exception as e:
            logger.error(f"Error subscribing to prices: {e}")
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

    async def _process_ws_message(
        self,
        stream_key: str,
        data: Dict[str, Any]
    ) -> None:
        """Process WebSocket message"""
        try:
            # Call handlers
            if stream_key in self._stream_handlers:
                for handler in self._stream_handlers[stream_key]:
                    try:
                        handler(data)
                    except Exception as e:
                        logger.error(f"Error in stream handler: {e}")
                        
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    async def unsubscribe_prices(self, instruments: List[str]) -> None:
        """
        Unsubscribe from price streams.
        
        Args:
            instruments: List of instruments
        """
        stream_key = f"prices_{'_'.join(instruments)}"
        if stream_key in self._ws_connections:
            ws = self._ws_connections[stream_key]
            await ws.close()
            del self._ws_connections[stream_key]
            logger.info(f"Unsubscribed from prices for {instruments}")

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
        """Close the Forex base connection"""
        if self._session:
            await self._session.close()
            self._session = None
        
        await self.close_websockets()
        
        self._price_cache.clear()
        self._candle_cache.clear()
        
        logger.info("ForexBase closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/v1/exchanges/forex", tags=["Forex"])


async def get_forex(
    api_key: str = Query(..., description="Forex API Key"),
    account_id: str = Query(..., description="Forex Account ID"),
    provider: ForexProvider = Query(ForexProvider.OANDA),
    environment: ForexEnvironment = Query(ForexEnvironment.PRACTICE)
) -> ForexBase:
    """Dependency to get ForexBase instance"""
    credentials = ForexCredentials(api_key=api_key, account_id=account_id, provider=provider)
    return ForexBase(credentials, environment)


@router.get("/account")
async def get_account_info(
    forex: ForexBase = Depends(get_forex)
):
    """Get account information"""
    return await forex.get_account_info()


@router.get("/instruments")
async def get_instruments(
    forex: ForexBase = Depends(get_forex)
):
    """Get available instruments"""
    return await forex.get_instruments()


@router.get("/price/{instrument}")
async def get_price(
    instrument: str,
    forex: ForexBase = Depends(get_forex)
):
    """Get current price for instrument"""
    return await forex.get_price(instrument)


@router.get("/candles/{instrument}")
async def get_candles(
    instrument: str,
    granularity: ForexGranularity = Query(ForexGranularity.H1),
    count: int = Query(500, le=1000),
    forex: ForexBase = Depends(get_forex)
):
    """Get candle data"""
    return await forex.get_candles(instrument, granularity, count)


@router.post("/order")
async def place_order(
    instrument: str = Query(...),
    side: ForexOrderSide = Query(...),
    units: float = Query(...),
    order_type: ForexOrderType = Query(ForexOrderType.MARKET),
    price: Optional[float] = Query(None),
    stop_loss: Optional[float] = Query(None),
    take_profit: Optional[float] = Query(None),
    forex: ForexBase = Depends(get_forex)
):
    """Place an order"""
    return await forex.place_order(
        instrument, side, units, order_type, price, stop_loss, take_profit
    )


@router.get("/positions")
async def get_positions(
    forex: ForexBase = Depends(get_forex)
):
    """Get open positions"""
    return await forex.get_positions()


@router.websocket("/ws")
async def forex_websocket(
    websocket: WebSocket,
    instruments: List[str] = Query(...),
    forex: ForexBase = Depends(get_forex)
):
    """WebSocket endpoint for price streams"""
    await websocket.accept()
    
    await forex.subscribe_prices(instruments)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await forex.unsubscribe_prices(instruments)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ForexBase',
    'ForexProvider',
    'ForexEnvironment',
    'ForexInstrumentType',
    'ForexGranularity',
    'ForexOrderType',
    'ForexOrderSide',
    'ForexTimeInForce',
    'ForexInstrument',
    'ForexPrice',
    'ForexCandle',
    'ForexOrderBook',
    'ForexPosition',
    'ForexCredentials',
    'ForexApiLimits',
    'ForexWebSocketMessage',
    'router'
]
