"""
NEXUS AI TRADING SYSTEM - Oanda Exchange Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/forex/oanda.py
Description: Oanda forex trading with full API integration
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

import aiohttp
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.exchange_config import ExchangeConfig
from shared.constants.trading_constants import ORDER_TYPES, POSITION_DIRECTIONS, TIME_FRAMES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

# Forex imports
from trading.exchanges.forex.base import (
    ForexBase,
    ForexProvider,
    ForexEnvironment,
    ForexInstrument,
    ForexPrice,
    ForexCandle,
    ForexPosition,
    ForexOrderType,
    ForexOrderSide,
    ForexTimeInForce
)
from trading.exchanges.forex.exceptions import (
    ForexException,
    ForexOrderError,
    ForexAccountError,
    ForexErrorCode,
    ForexErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class OandaOrderType(str, Enum):
    """Oanda order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"


class OandaOrderSide(str, Enum):
    """Oanda order sides"""
    BUY = "buy"
    SELL = "sell"


class OandaTimeInForce(str, Enum):
    """Oanda time in force"""
    GTC = "GTC"
    DAY = "DAY"
    IOC = "IOC"
    FOK = "FOK"


class OandaOrderStatus(str, Enum):
    """Oanda order status"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OandaPositionSide(str, Enum):
    """Oanda position sides"""
    LONG = "long"
    SHORT = "short"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OandaAccountInfo(BaseModel):
    """Oanda account information"""
    account_id: str
    balance: float
    equity: float
    margin_used: float
    margin_available: float
    leverage: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class OandaOrderRequest(BaseModel):
    """Oanda order request"""
    instrument: str
    side: OandaOrderSide
    order_type: OandaOrderType = OandaOrderType.LIMIT
    units: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: OandaTimeInForce = OandaTimeInForce.GTC
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    client_order_id: Optional[str] = None


class OandaOrderResponse(BaseModel):
    """Oanda order response"""
    order_id: str
    client_order_id: str
    instrument: str
    side: OandaOrderSide
    order_type: OandaOrderType
    status: OandaOrderStatus
    units: float
    filled_units: float
    price: float
    avg_price: float
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: OandaTimeInForce
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class OandaCredentials:
    """Oanda API credentials"""
    api_key: str
    account_id: str


# =============================================================================
# OANDA EXCHANGE
# =============================================================================

class OandaExchange(ForexBase):
    """
    Oanda Exchange with full API integration.
    
    Features:
    - Account management
    - Order management (market, limit, stop, stop-limit, trailing stop)
    - Position management
    - Market data
    - WebSocket streams
    - Balance management
    - Risk management
    """

    BASE_URL = "https://api-fxtrade.oanda.com"
    DEMO_BASE_URL = "https://api-fxpractice.oanda.com"

    def __init__(
        self,
        credentials: OandaCredentials,
        environment: ForexEnvironment = ForexEnvironment.PRACTICE,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize OandaExchange.
        
        Args:
            credentials: Oanda API credentials
            environment: Forex environment
            config: Exchange configuration
        """
        # Create Forex credentials
        forex_credentials = ForexCredentials(
            api_key=credentials.api_key,
            account_id=credentials.account_id,
            provider=ForexProvider.OANDA
        )
        
        super().__init__(forex_credentials, environment, config)
        
        self.oanda_credentials = credentials
        
        # Base URL
        if environment == ForexEnvironment.PRODUCTION:
            self.base_url = self.BASE_URL
        else:
            self.base_url = self.DEMO_BASE_URL
        
        # Error handler
        self._error_handler = ForexErrorHandler()
        
        # Cache
        self._order_cache: Dict[str, OandaOrderResponse] = {}
        self._position_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("OandaExchange initialized")

    # =========================================================================
    # Account Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_account_info(self) -> OandaAccountInfo:
        """
        Get account information.
        
        Returns:
            OandaAccountInfo: Account information
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/v3/accounts/' + self.oanda_credentials.account_id + '/summary'
            )
            
            data = response.get('account', {})
            
            return OandaAccountInfo(
                account_id=self.oanda_credentials.account_id,
                balance=float(data.get('balance', 0)),
                equity=float(data.get('NAV', 0)),
                margin_used=float(data.get('marginUsed', 0)),
                margin_available=float(data.get('marginAvailable', 0)),
                leverage=float(data.get('marginRate', 0.02)) * 100,
                positions=[],
                orders=[],
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            raise

    # =========================================================================
    # Order Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: OandaOrderRequest
    ) -> OandaOrderResponse:
        """
        Place an order.
        
        Args:
            request: Order request
            
        Returns:
            OandaOrderResponse: Order response
        """
        try:
            # Prepare order data
            order_data = {
                'order': {
                    'instrument': request.instrument,
                    'units': str(request.units),
                    'type': request.order_type.value,
                    'timeInForce': request.time_in_force.value
                }
            }
            
            if request.side == OandaOrderSide.BUY:
                order_data['order']['positionFill'] = 'DEFAULT'
            
            if request.price:
                order_data['order']['price'] = str(request.price)
            
            if request.stop_price:
                order_data['order']['stopPrice'] = str(request.stop_price)
            
            if request.limit_price:
                order_data['order']['limitPrice'] = str(request.limit_price)
            
            if request.stop_loss:
                order_data['order']['stopLossOnFill'] = {
                    'price': str(request.stop_loss),
                    'timeInForce': request.time_in_force.value
                }
            
            if request.take_profit:
                order_data['order']['takeProfitOnFill'] = {
                    'price': str(request.take_profit),
                    'timeInForce': request.time_in_force.value
                }
            
            if request.trailing_stop:
                order_data['order']['trailingStopLossOnFill'] = {
                    'distance': str(request.trailing_stop),
                    'timeInForce': request.time_in_force.value
                }
            
            if request.client_order_id:
                order_data['order']['clientExtensions'] = {
                    'id': request.client_order_id
                }
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/v3/accounts/' + self.oanda_credentials.account_id + '/orders',
                data=order_data,
                signed=True
            )
            
            result = response.get('orderCreateTransaction', {})
            fill = response.get('orderFillTransaction', {})
            
            # Parse response
            order_response = OandaOrderResponse(
                order_id=result.get('id', ''),
                client_order_id=request.client_order_id or '',
                instrument=result.get('instrument', request.instrument),
                side=OandaOrderSide(request.side.value),
                order_type=OandaOrderType(result.get('type', request.order_type.value)),
                status=OandaOrderStatus(result.get('status', 'PENDING')),
                units=float(result.get('units', request.units)),
                filled_units=float(fill.get('units', 0)),
                price=float(result.get('price', request.price or 0)),
                avg_price=float(fill.get('price', 0)),
                stop_price=float(result.get('stopPrice')) if result.get('stopPrice') else None,
                limit_price=float(result.get('limitPrice')) if result.get('limitPrice') else None,
                time_in_force=OandaTimeInForce(result.get('timeInForce', request.time_in_force.value)),
                stop_loss=float(result.get('stopLossOnFill', {}).get('price')) if result.get('stopLossOnFill') else None,
                take_profit=float(result.get('takeProfitOnFill', {}).get('price')) if result.get('takeProfitOnFill') else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Cache order
            self._order_cache[order_response.order_id] = order_response
            
            logger.info(f"Order placed: {order_response.order_id} for {request.instrument}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            bool: Success indicator
        """
        try:
            await self._request(
                method='PUT',
                endpoint='/v3/accounts/' + self.oanda_credentials.account_id + '/orders/' + order_id + '/cancel',
                signed=True
            )
            
            # Remove from cache
            if order_id in self._order_cache:
                del self._order_cache[order_id]
            
            logger.info(f"Order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order(self, order_id: str) -> Optional[OandaOrderResponse]:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            
        Returns:
            Optional[OandaOrderResponse]: Order details
        """
        try:
            # Check cache
            if order_id in self._order_cache:
                return self._order_cache[order_id]
            
            response = await self._request(
                method='GET',
                endpoint='/v3/accounts/' + self.oanda_credentials.account_id + '/orders/' + order_id,
                signed=True
            )
            
            result = response.get('order', {})
            
            order_response = OandaOrderResponse(
                order_id=result.get('id', ''),
                client_order_id=result.get('clientExtensions', {}).get('id', ''),
                instrument=result.get('instrument', ''),
                side=OandaOrderSide(result.get('side', 'buy')),
                order_type=OandaOrderType(result.get('type', 'LIMIT')),
                status=OandaOrderStatus(result.get('status', 'PENDING')),
                units=float(result.get('units', 0)),
                filled_units=0,
                price=float(result.get('price', 0)),
                avg_price=0,
                stop_price=float(result.get('stopPrice')) if result.get('stopPrice') else None,
                limit_price=float(result.get('limitPrice')) if result.get('limitPrice') else None,
                time_in_force=OandaTimeInForce(result.get('timeInForce', 'GTC')),
                stop_loss=float(result.get('stopLossOnFill', {}).get('price')) if result.get('stopLossOnFill') else None,
                take_profit=float(result.get('takeProfitOnFill', {}).get('price')) if result.get('takeProfitOnFill') else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Cache
            self._order_cache[order_response.order_id] = order_response
            
            return order_response
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    # =========================================================================
    # Position Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_positions(self) -> List[ForexPosition]:
        """
        Get open positions.
        
        Returns:
            List[ForexPosition]: Positions
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/v3/accounts/' + self.oanda_credentials.account_id + '/positions',
                signed=True
            )
            
            positions = []
            for data in response.get('positions', []):
                instrument = data.get('instrument', '')
                long = data.get('long', {})
                short = data.get('short', {})
                
                if float(long.get('units', 0)) != 0:
                    position = ForexPosition(
                        instrument=instrument,
                        units=float(long.get('units', 0)),
                        average_price=float(long.get('averagePrice', 0)),
                        unrealized_pnl=float(long.get('unrealizedPL', 0)),
                        realized_pnl=0,
                        side='long',
                        timestamp=datetime.utcnow()
                    )
                    positions.append(position)
                
                if float(short.get('units', 0)) != 0:
                    position = ForexPosition(
                        instrument=instrument,
                        units=float(short.get('units', 0)),
                        average_price=float(short.get('averagePrice', 0)),
                        unrealized_pnl=float(short.get('unrealizedPL', 0)),
                        realized_pnl=0,
                        side='short',
                        timestamp=datetime.utcnow()
                    )
                    positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            raise

    # =========================================================================
    # Market Data
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_price(self, instrument: str) -> ForexPrice:
        """
        Get current price for instrument.
        
        Args:
            instrument: Instrument name
            
        Returns:
            ForexPrice: Price data
        """
        try:
            params = {'instruments': instrument}
            
            response = await self._request(
                method='GET',
                endpoint='/v3/accounts/' + self.oanda_credentials.account_id + '/pricing',
                params=params
            )
            
            data = response.get('prices', [])[0]
            
            return ForexPrice(
                instrument=data.get('instrument', instrument),
                bid=float(data.get('bids', [{'price': 0}])[0].get('price', 0)),
                ask=float(data.get('asks', [{'price': 0}])[0].get('price', 0)),
                spread=float(data.get('bids', [{'price': 0}])[0].get('price', 0)) - float(data.get('asks', [{'price': 0}])[0].get('price', 0)),
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting price for {instrument}: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def get_candles(
        self,
        instrument: str,
        granularity: str = 'H1',
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
                'granularity': granularity,
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
                    granularity=granularity,
                    timestamp=datetime.utcnow(),
                    open=float(mid.get('o', 0)),
                    high=float(mid.get('h', 0)),
                    low=float(mid.get('l', 0)),
                    close=float(mid.get('c', 0)),
                    volume=int(data.get('volume', 0)),
                    complete=data.get('complete', True)
                ))
            
            return candles
            
        except Exception as e:
            logger.error(f"Error getting candles for {instrument}: {e}")
            raise

    # =========================================================================
    # Private Methods
    # =========================================================================

    async def _authenticate(self) -> None:
        """Authenticate API session"""
        # Oanda uses API key authentication
        pass

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Oanda exchange connection"""
        await super().close()
        
        self._order_cache.clear()
        self._position_cache.clear()
        
        logger.info("OandaExchange closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/forex/oanda", tags=["Forex Oanda"])


async def get_exchange(
    api_key: str = Query(..., description="Oanda API Key"),
    account_id: str = Query(..., description="Oanda Account ID"),
    environment: ForexEnvironment = Query(ForexEnvironment.PRACTICE)
) -> OandaExchange:
    """Dependency to get OandaExchange instance"""
    credentials = OandaCredentials(
        api_key=api_key,
        account_id=account_id
    )
    return OandaExchange(credentials, environment)


@router.get("/account")
async def get_account_info(
    exchange: OandaExchange = Depends(get_exchange)
):
    """Get account information"""
    return await exchange.get_account_info()


@router.post("/order")
async def place_order(
    request: OandaOrderRequest,
    exchange: OandaExchange = Depends(get_exchange)
):
    """Place an order"""
    return await exchange.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    exchange: OandaExchange = Depends(get_exchange)
):
    """Cancel an order"""
    success = await exchange.cancel_order(order_id)
    return {"success": success}


@router.get("/order/{order_id}")
async def get_order(
    order_id: str,
    exchange: OandaExchange = Depends(get_exchange)
):
    """Get order details"""
    return await exchange.get_order(order_id)


@router.get("/positions")
async def get_positions(
    exchange: OandaExchange = Depends(get_exchange)
):
    """Get open positions"""
    return await exchange.get_positions()


@router.get("/price/{instrument}")
async def get_price(
    instrument: str,
    exchange: OandaExchange = Depends(get_exchange)
):
    """Get current price for instrument"""
    return await exchange.get_price(instrument)


@router.get("/candles/{instrument}")
async def get_candles(
    instrument: str,
    granularity: str = Query("H1"),
    count: int = Query(500, le=1000),
    exchange: OandaExchange = Depends(get_exchange)
):
    """Get candle data"""
    return await exchange.get_candles(instrument, granularity, count)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OandaExchange',
    'OandaOrderType',
    'OandaOrderSide',
    'OandaTimeInForce',
    'OandaOrderStatus',
    'OandaPositionSide',
    'OandaAccountInfo',
    'OandaOrderRequest',
    'OandaOrderResponse',
    'OandaCredentials',
    'router'
]
