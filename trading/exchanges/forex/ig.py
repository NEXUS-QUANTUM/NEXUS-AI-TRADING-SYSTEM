"""
NEXUS AI TRADING SYSTEM - IG Exchange Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/forex/ig.py
Description: IG forex and CFD trading with full API integration
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

class IGOrderType(str, Enum):
    """IG order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"  # One Cancels Other
    BRACKET = "bracket"  # Bracket order


class IGOrderSide(str, Enum):
    """IG order sides"""
    BUY = "buy"
    SELL = "sell"


class IGTimeInForce(str, Enum):
    """IG time in force"""
    GTC = "gtc"
    DAY = "day"
    IOC = "ioc"
    FOK = "fok"


class IGOrderStatus(str, Enum):
    """IG order status"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class IGDealStatus(str, Enum):
    """IG deal status"""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class IGAccountInfo(BaseModel):
    """IG account information"""
    account_id: str
    balance: float
    equity: float
    margin_used: float
    margin_available: float
    leverage: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class IGOrderRequest(BaseModel):
    """IG order request"""
    instrument: str
    side: IGOrderSide
    order_type: IGOrderType = IGOrderType.LIMIT
    units: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: IGTimeInForce = IGTimeInForce.GTC
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    client_order_id: Optional[str] = None
    guaranteed_stop: bool = False


class IGOrderResponse(BaseModel):
    """IG order response"""
    order_id: str
    client_order_id: str
    instrument: str
    side: IGOrderSide
    order_type: IGOrderType
    status: IGOrderStatus
    units: float
    filled_units: float
    price: float
    avg_price: float
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: IGTimeInForce
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    deal_reference: str
    created_at: datetime
    updated_at: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class IGCredentials:
    """IG API credentials"""
    api_key: str
    username: str
    password: str
    account_id: str


@dataclass
class IGSession:
    """IG session data"""
    token: str
    expires_at: datetime
    account_id: str


# =============================================================================
# IG EXCHANGE
# =============================================================================

class IGExchange(ForexBase):
    """
    IG Exchange with full API integration.
    
    Features:
    - Account management
    - Order management (market, limit, stop, stop-limit, trailing stop, OCO, bracket)
    - Position management
    - Market data
    - WebSocket streams
    - Balance management
    - Risk management
    - Guaranteed stop loss
    """

    BASE_URL = "https://api.ig.com"
    DEMO_BASE_URL = "https://demo-api.ig.com"
    WS_URL = "wss://ws-api.ig.com"

    def __init__(
        self,
        credentials: IGCredentials,
        environment: ForexEnvironment = ForexEnvironment.PRACTICE,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize IGExchange.
        
        Args:
            credentials: IG API credentials
            environment: Forex environment
            config: Exchange configuration
        """
        # Create Forex credentials
        forex_credentials = ForexCredentials(
            api_key=credentials.api_key,
            account_id=credentials.account_id,
            provider=ForexProvider.IG
        )
        
        super().__init__(forex_credentials, environment, config)
        
        self.ig_credentials = credentials
        
        # Base URL
        if environment == ForexEnvironment.PRODUCTION:
            self.base_url = self.BASE_URL
        else:
            self.base_url = self.DEMO_BASE_URL
        
        # Session
        self._session_data: Optional[IGSession] = None
        
        # Error handler
        self._error_handler = ForexErrorHandler()
        
        # Cache
        self._order_cache: Dict[str, IGOrderResponse] = {}
        self._position_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("IGExchange initialized")

    # =========================================================================
    # Authentication
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def authenticate(self) -> str:
        """
        Authenticate with IG API.
        
        Returns:
            str: Access token
        """
        try:
            auth_data = {
                'identifier': self.ig_credentials.username,
                'password': self.ig_credentials.password
            }
            
            headers = {
                'X-IG-API-KEY': self.ig_credentials.api_key,
                'Content-Type': 'application/json'
            }
            
            response = await self._request(
                method='POST',
                endpoint='/v3/session',
                data=auth_data,
                headers=headers
            )
            
            token = response.get('oauthToken', {}).get('access_token')
            expires_in = response.get('oauthToken', {}).get('expires_in', 3600)
            
            self._session_data = IGSession(
                token=token,
                expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
                account_id=self.ig_credentials.account_id
            )
            
            logger.info("IG authentication successful")
            return token
            
        except Exception as e:
            logger.error(f"Error authenticating with IG: {e}")
            raise

    # =========================================================================
    # Account Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_account_info(self) -> IGAccountInfo:
        """
        Get account information.
        
        Returns:
            IGAccountInfo: Account information
        """
        try:
            # Ensure authentication
            if not self._session_data or datetime.utcnow() > self._session_data.expires_at:
                await self.authenticate()
            
            headers = {
                'X-IG-API-KEY': self.ig_credentials.api_key,
                'X-SECURITY-TOKEN': self._session_data.token
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v3/accounts/' + self.ig_credentials.account_id,
                headers=headers
            )
            
            data = response
            
            return IGAccountInfo(
                account_id=self.ig_credentials.account_id,
                balance=float(data.get('balance', {}).get('available', 0)),
                equity=float(data.get('balance', {}).get('equity', 0)),
                margin_used=float(data.get('balance', {}).get('usedMargin', 0)),
                margin_available=float(data.get('balance', {}).get('availableToTrade', 0)),
                leverage=30.0,
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
        request: IGOrderRequest
    ) -> IGOrderResponse:
        """
        Place an order.
        
        Args:
            request: Order request
            
        Returns:
            IGOrderResponse: Order response
        """
        try:
            # Ensure authentication
            if not self._session_data or datetime.utcnow() > self._session_data.expires_at:
                await self.authenticate()
            
            # Prepare order data
            order_data = {
                'epic': request.instrument,
                'direction': request.side.value.upper(),
                'orderType': request.order_type.value.upper(),
                'size': str(request.units),
                'timeInForce': request.time_in_force.value.upper(),
                'guaranteedStop': request.guaranteed_stop
            }
            
            if request.price:
                order_data['level'] = str(request.price)
            
            if request.stop_price:
                order_data['stopLevel'] = str(request.stop_price)
            
            if request.limit_price:
                order_data['limitLevel'] = str(request.limit_price)
            
            if request.stop_loss:
                order_data['stopLoss'] = str(request.stop_loss)
            
            if request.take_profit:
                order_data['takeProfit'] = str(request.take_profit)
            
            if request.trailing_stop:
                order_data['trailingStop'] = str(request.trailing_stop)
            
            headers = {
                'X-IG-API-KEY': self.ig_credentials.api_key,
                'X-SECURITY-TOKEN': self._session_data.token,
                'Content-Type': 'application/json',
                'Version': '3'
            }
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/v3/positions/otc',
                data=order_data,
                headers=headers
            )
            
            result = response
            
            # Parse response
            order_response = IGOrderResponse(
                order_id=result.get('dealReference', ''),
                client_order_id=request.client_order_id or '',
                instrument=request.instrument,
                side=request.side,
                order_type=request.order_type,
                status=IGOrderStatus.PENDING,
                units=request.units,
                filled_units=0,
                price=request.price or 0,
                avg_price=0,
                stop_price=request.stop_price,
                limit_price=request.limit_price,
                time_in_force=request.time_in_force,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                deal_reference=result.get('dealReference', ''),
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
            # Ensure authentication
            if not self._session_data or datetime.utcnow() > self._session_data.expires_at:
                await self.authenticate()
            
            headers = {
                'X-IG-API-KEY': self.ig_credentials.api_key,
                'X-SECURITY-TOKEN': self._session_data.token,
                'Version': '3'
            }
            
            await self._request(
                method='DELETE',
                endpoint=f'/v3/positions/otc/{order_id}',
                headers=headers
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
    async def get_order(self, order_id: str) -> Optional[IGOrderResponse]:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            
        Returns:
            Optional[IGOrderResponse]: Order details
        """
        try:
            # Check cache
            if order_id in self._order_cache:
                return self._order_cache[order_id]
            
            # Ensure authentication
            if not self._session_data or datetime.utcnow() > self._session_data.expires_at:
                await self.authenticate()
            
            headers = {
                'X-IG-API-KEY': self.ig_credentials.api_key,
                'X-SECURITY-TOKEN': self._session_data.token,
                'Version': '3'
            }
            
            response = await self._request(
                method='GET',
                endpoint=f'/v3/positions/otc/{order_id}',
                headers=headers
            )
            
            result = response
            
            order_response = IGOrderResponse(
                order_id=result.get('dealId', ''),
                client_order_id=result.get('clientId', ''),
                instrument=result.get('instrument', {}).get('epic', ''),
                side=IGOrderSide(result.get('direction', 'buy').lower()),
                order_type=IGOrderType(result.get('orderType', 'limit').lower()),
                status=IGOrderStatus(result.get('status', 'pending').lower()),
                units=float(result.get('size', 0)),
                filled_units=float(result.get('filledSize', 0)),
                price=float(result.get('level', 0)),
                avg_price=float(result.get('avgPrice', 0)),
                stop_price=float(result.get('stopLevel')) if result.get('stopLevel') else None,
                limit_price=float(result.get('limitLevel')) if result.get('limitLevel') else None,
                time_in_force=IGTimeInForce(result.get('timeInForce', 'gtc').lower()),
                stop_loss=float(result.get('stopLoss')) if result.get('stopLoss') else None,
                take_profit=float(result.get('takeProfit')) if result.get('takeProfit') else None,
                deal_reference=result.get('dealReference', ''),
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
            # Ensure authentication
            if not self._session_data or datetime.utcnow() > self._session_data.expires_at:
                await self.authenticate()
            
            headers = {
                'X-IG-API-KEY': self.ig_credentials.api_key,
                'X-SECURITY-TOKEN': self._session_data.token,
                'Version': '3'
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v3/positions',
                headers=headers
            )
            
            positions = []
            for data in response.get('positions', []):
                position = ForexPosition(
                    instrument=data.get('market', {}).get('epic', ''),
                    units=float(data.get('position', {}).get('size', 0)),
                    average_price=float(data.get('position', {}).get('level', 0)),
                    unrealized_pnl=float(data.get('position', {}).get('unrealised', 0)),
                    realized_pnl=float(data.get('position', {}).get('realised', 0)),
                    side=data.get('position', {}).get('direction', 'buy').lower(),
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
            # Ensure authentication
            if not self._session_data or datetime.utcnow() > self._session_data.expires_at:
                await self.authenticate()
            
            headers = {
                'X-IG-API-KEY': self.ig_credentials.api_key,
                'X-SECURITY-TOKEN': self._session_data.token,
                'Version': '3'
            }
            
            response = await self._request(
                method='GET',
                endpoint=f'/v3/prices/{instrument}',
                headers=headers
            )
            
            data = response
            
            return ForexPrice(
                instrument=instrument,
                bid=float(data.get('bid', 0)),
                ask=float(data.get('ask', 0)),
                spread=float(data.get('spread', 0)),
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
            # Ensure authentication
            if not self._session_data or datetime.utcnow() > self._session_data.expires_at:
                await self.authenticate()
            
            params = {
                'granularity': granularity,
                'count': count
            }
            
            headers = {
                'X-IG-API-KEY': self.ig_credentials.api_key,
                'X-SECURITY-TOKEN': self._session_data.token,
                'Version': '3'
            }
            
            response = await self._request(
                method='GET',
                endpoint=f'/v3/prices/{instrument}',
                params=params,
                headers=headers
            )
            
            candles = []
            for data in response.get('candles', []):
                candles.append(ForexCandle(
                    instrument=instrument,
                    granularity=granularity,
                    timestamp=datetime.utcnow(),
                    open=float(data.get('open', {}).get('bid', 0)),
                    high=float(data.get('high', {}).get('bid', 0)),
                    low=float(data.get('low', {}).get('bid', 0)),
                    close=float(data.get('close', {}).get('bid', 0)),
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

    async def _ensure_authentication(self) -> None:
        """Ensure valid authentication"""
        if not self._session_data or datetime.utcnow() > self._session_data.expires_at:
            await self.authenticate()

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the IG exchange connection"""
        await super().close()
        
        self._order_cache.clear()
        self._position_cache.clear()
        
        # Logout
        if self._session_data:
            try:
                headers = {
                    'X-IG-API-KEY': self.ig_credentials.api_key,
                    'X-SECURITY-TOKEN': self._session_data.token
                }
                await self._request(
                    method='DELETE',
                    endpoint='/v3/session',
                    headers=headers
                )
            except Exception as e:
                logger.warning(f"Error logging out: {e}")
        
        logger.info("IGExchange closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/forex/ig", tags=["Forex IG"])


async def get_exchange(
    api_key: str = Query(..., description="IG API Key"),
    username: str = Query(..., description="IG Username"),
    password: str = Query(..., description="IG Password"),
    account_id: str = Query(..., description="IG Account ID"),
    environment: ForexEnvironment = Query(ForexEnvironment.PRACTICE)
) -> IGExchange:
    """Dependency to get IGExchange instance"""
    credentials = IGCredentials(
        api_key=api_key,
        username=username,
        password=password,
        account_id=account_id
    )
    return IGExchange(credentials, environment)


@router.post("/auth")
async def authenticate(
    exchange: IGExchange = Depends(get_exchange)
):
    """Authenticate with IG"""
    token = await exchange.authenticate()
    return {"token": token}


@router.get("/account")
async def get_account_info(
    exchange: IGExchange = Depends(get_exchange)
):
    """Get account information"""
    return await exchange.get_account_info()


@router.post("/order")
async def place_order(
    request: IGOrderRequest,
    exchange: IGExchange = Depends(get_exchange)
):
    """Place an order"""
    return await exchange.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    exchange: IGExchange = Depends(get_exchange)
):
    """Cancel an order"""
    success = await exchange.cancel_order(order_id)
    return {"success": success}


@router.get("/order/{order_id}")
async def get_order(
    order_id: str,
    exchange: IGExchange = Depends(get_exchange)
):
    """Get order details"""
    return await exchange.get_order(order_id)


@router.get("/positions")
async def get_positions(
    exchange: IGExchange = Depends(get_exchange)
):
    """Get open positions"""
    return await exchange.get_positions()


@router.get("/price/{instrument}")
async def get_price(
    instrument: str,
    exchange: IGExchange = Depends(get_exchange)
):
    """Get current price for instrument"""
    return await exchange.get_price(instrument)


@router.get("/candles/{instrument}")
async def get_candles(
    instrument: str,
    granularity: str = Query("H1"),
    count: int = Query(500, le=1000),
    exchange: IGExchange = Depends(get_exchange)
):
    """Get candle data"""
    return await exchange.get_candles(instrument, granularity, count)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'IGExchange',
    'IGOrderType',
    'IGOrderSide',
    'IGTimeInForce',
    'IGOrderStatus',
    'IGDealStatus',
    'IGAccountInfo',
    'IGOrderRequest',
    'IGOrderResponse',
    'IGCredentials',
    'IGSession',
    'router'
]
