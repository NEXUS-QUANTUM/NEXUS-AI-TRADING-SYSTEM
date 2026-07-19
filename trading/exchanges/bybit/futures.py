"""
NEXUS AI TRADING SYSTEM - Bybit Futures Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/futures.py
Description: Bybit futures trading with full API integration
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

import aiohttp
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.exchange_config import ExchangeConfig
from shared.constants.trading_constants import ORDER_TYPES, POSITION_DIRECTIONS
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

# Bybit imports
from trading.exchanges.bybit.base import BybitBase, BybitEnvironment, BybitCategory, BybitInterval
from trading.exchanges.bybit.account import (
    BybitAccount,
    BybitCredentials,
    BybitAccountInfo,
    BybitBalance,
    BybitOrderRequest,
    BybitOrderResponse,
    BybitOrderSide,
    BybitOrderType,
    BybitOrderStatus,
    BybitTimeInForce,
    BybitMarginMode
)
from trading.exchanges.bybit.exceptions import (
    BybitException,
    BybitOrderError,
    BybitAccountError,
    BybitErrorCode,
    BybitErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BybitFuturesType(str, Enum):
    """Bybit futures types"""
    LINEAR = "linear"  # USDT perpetual
    INVERSE = "inverse"  # Coin-margined


class BybitFuturesOrderType(str, Enum):
    """Bybit futures order types"""
    LIMIT = "Limit"
    MARKET = "Market"
    STOP = "Stop"
    STOP_LIMIT = "StopLimit"
    TAKE_PROFIT = "TakeProfit"
    TAKE_PROFIT_LIMIT = "TakeProfitLimit"
    TRAILING_STOP = "TrailingStop"


class BybitFuturesOrderSide(str, Enum):
    """Bybit futures order sides"""
    BUY = "Buy"
    SELL = "Sell"


class BybitFuturesPositionSide(str, Enum):
    """Bybit futures position sides"""
    BOTH = "Both"
    LONG = "Long"
    SHORT = "Short"


class BybitFuturesTimeInForce(str, Enum):
    """Bybit futures time in force"""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "PostOnly"


class BybitFuturesMarginMode(str, Enum):
    """Bybit futures margin modes"""
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BybitFuturesAccountInfo(BaseModel):
    """Bybit futures account information"""
    account_id: str
    account_type: str
    total_equity: float
    available_balance: float
    used_margin: float
    margin_ratio: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class BybitFuturesPosition(BaseModel):
    """Bybit futures position"""
    symbol: str
    position_side: BybitFuturesPositionSide
    entry_price: float
    mark_price: float
    position_value: float
    position_size: float
    unrealized_pnl: float
    realized_pnl: float
    leverage: int
    liquidation_price: float
    margin_type: str
    timestamp: datetime


class BybitFuturesOrderRequest(BaseModel):
    """Bybit futures order request"""
    symbol: str
    side: BybitFuturesOrderSide
    position_side: BybitFuturesPositionSide = BybitFuturesPositionSide.BOTH
    order_type: BybitFuturesOrderType = BybitFuturesOrderType.LIMIT
    qty: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: BybitFuturesTimeInForce = BybitFuturesTimeInForce.GTC
    reduce_only: bool = False
    close_on_trigger: bool = False
    position_idx: int = 0
    order_link_id: Optional[str] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    tp_trigger_by: Optional[str] = None
    sl_trigger_by: Optional[str] = None
    tpsl_mode: str = "Full"


class BybitFuturesOrderResponse(BaseModel):
    """Bybit futures order response"""
    order_id: str
    order_link_id: str
    symbol: str
    side: BybitFuturesOrderSide
    position_side: BybitFuturesPositionSide
    order_type: BybitFuturesOrderType
    status: BybitOrderStatus
    price: float
    avg_price: float
    qty: float
    cum_exec_qty: float
    cum_exec_value: float
    time_in_force: BybitFuturesTimeInForce
    stop_price: Optional[float] = None
    reduce_only: bool
    close_on_trigger: bool
    created_at: datetime
    updated_at: datetime


class BybitFuturesLeverageRequest(BaseModel):
    """Bybit futures leverage request"""
    symbol: str
    leverage: int = 1
    margin_mode: BybitFuturesMarginMode = BybitFuturesMarginMode.ISOLATED


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BybitFuturesStreamConfig:
    """Bybit futures stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BYBIT FUTURES
# =============================================================================

class BybitFutures(BybitBase):
    """
    Bybit Futures Trading with full API integration.
    
    Features:
    - Futures trading (linear and inverse)
    - Position management
    - Leverage management
    - Margin management
    - Order management
    - Market data
    - WebSocket streams
    - Account management
    - Risk management
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: BybitEnvironment = BybitEnvironment.TESTNET,
        futures_type: BybitFuturesType = BybitFuturesType.LINEAR,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BybitFutures.
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            environment: Bybit environment
            futures_type: Futures type
            config: Exchange configuration
        """
        super().__init__(
            api_key,
            api_secret,
            environment,
            BybitCategory.LINEAR if futures_type == BybitFuturesType.LINEAR else BybitCategory.INVERSE,
            config
        )
        
        self.futures_type = futures_type
        
        # Error handler
        self._error_handler = BybitErrorHandler()
        
        # Position cache
        self._position_cache: Dict[str, BybitFuturesPosition] = {}
        
        # Leverage cache
        self._leverage_cache: Dict[str, int] = {}
        
        # Margin mode cache
        self._margin_mode_cache: Dict[str, str] = {}
        
        logger.info(f"BybitFutures initialized for {futures_type.value}")

    # =========================================================================
    # Account Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_account_info(self) -> BybitFuturesAccountInfo:
        """
        Get futures account information.
        
        Returns:
            BybitFuturesAccountInfo: Account information
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/v5/account/info',
                signed=True
            )
            
            data = response
            
            return BybitFuturesAccountInfo(
                account_id=data.get('accountId', ''),
                account_type=data.get('accountType', ''),
                total_equity=float(data.get('totalEquity', 0)),
                available_balance=float(data.get('availableBalance', 0)),
                used_margin=float(data.get('usedMargin', 0)),
                margin_ratio=float(data.get('marginRatio', 0)),
                positions=data.get('positions', []),
                orders=data.get('orders', []),
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting futures account info: {e}")
            raise

    # =========================================================================
    # Position Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_positions(self, symbol: Optional[str] = None) -> List[BybitFuturesPosition]:
        """
        Get futures positions.
        
        Args:
            symbol: Symbol (optional)
            
        Returns:
            List[BybitFuturesPosition]: Positions
        """
        try:
            params = {}
            if symbol:
                params['symbol'] = symbol
            
            response = await self._request(
                method='GET',
                endpoint='/v5/position/list',
                params=params,
                signed=True
            )
            
            positions = []
            for data in response.get('list', []):
                position = BybitFuturesPosition(
                    symbol=data.get('symbol'),
                    position_side=BybitFuturesPositionSide(data.get('side', 'Both')),
                    entry_price=float(data.get('avgPrice', 0)),
                    mark_price=float(data.get('markPrice', 0)),
                    position_value=float(data.get('positionValue', 0)),
                    position_size=float(data.get('size', 0)),
                    unrealized_pnl=float(data.get('unrealisedPnl', 0)),
                    realized_pnl=float(data.get('realisedPnl', 0)),
                    leverage=int(data.get('leverage', 1)),
                    liquidation_price=float(data.get('liqPrice', 0)),
                    margin_type=data.get('marginMode', 'ISOLATED'),
                    timestamp=datetime.utcnow()
                )
                positions.append(position)
                
                # Cache
                self._position_cache[position.symbol] = position
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting futures positions: {e}")
            raise

    # =========================================================================
    # Leverage Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def set_leverage(
        self,
        symbol: str,
        leverage: int,
        margin_mode: BybitFuturesMarginMode = BybitFuturesMarginMode.ISOLATED
    ) -> bool:
        """
        Set leverage for a symbol.
        
        Args:
            symbol: Symbol
            leverage: Leverage (1-100)
            margin_mode: Margin mode
            
        Returns:
            bool: Success indicator
        """
        try:
            data = {
                'symbol': symbol,
                'leverage': str(leverage),
                'marginMode': margin_mode.value
            }
            
            response = await self._request(
                method='POST',
                endpoint='/v5/position/set-leverage',
                data=data,
                signed=True
            )
            
            # Cache
            self._leverage_cache[symbol] = leverage
            self._margin_mode_cache[symbol] = margin_mode.value
            
            logger.info(f"Leverage set for {symbol}: {leverage}x ({margin_mode.value})")
            return True
            
        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            return False

    async def get_leverage(self, symbol: str) -> int:
        """
        Get leverage for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            int: Leverage
        """
        try:
            # Check cache
            if symbol in self._leverage_cache:
                return self._leverage_cache[symbol]
            
            # Get positions to find leverage
            positions = await self.get_positions(symbol)
            for pos in positions:
                if pos.symbol == symbol:
                    self._leverage_cache[symbol] = pos.leverage
                    return pos.leverage
            
            return 1
            
        except Exception as e:
            logger.error(f"Error getting leverage: {e}")
            return 1

    # =========================================================================
    # Order Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: BybitFuturesOrderRequest
    ) -> BybitFuturesOrderResponse:
        """
        Place a futures order.
        
        Args:
            request: Order request
            
        Returns:
            BybitFuturesOrderResponse: Order response
        """
        try:
            # Prepare order data
            data = {
                'symbol': request.symbol,
                'side': request.side.value,
                'orderType': request.order_type.value,
                'qty': str(request.qty),
                'timeInForce': request.time_in_force.value,
                'positionIdx': request.position_idx
            }
            
            if request.price:
                data['price'] = str(request.price)
            
            if request.stop_price:
                data['stopPrice'] = str(request.stop_price)
            
            if request.reduce_only:
                data['reduceOnly'] = True
            
            if request.close_on_trigger:
                data['closeOnTrigger'] = True
            
            if request.order_link_id:
                data['orderLinkId'] = request.order_link_id
            
            if request.take_profit:
                data['takeProfit'] = str(request.take_profit)
            
            if request.stop_loss:
                data['stopLoss'] = str(request.stop_loss)
            
            if request.tpsl_mode:
                data['tpslMode'] = request.tpsl_mode
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/v5/order/create',
                data=data,
                signed=True
            )
            
            result = response
            
            # Parse response
            order_response = BybitFuturesOrderResponse(
                order_id=result.get('orderId'),
                order_link_id=result.get('orderLinkId', ''),
                symbol=result.get('symbol'),
                side=BybitFuturesOrderSide(result.get('side')),
                position_side=BybitFuturesPositionSide(result.get('positionSide', 'Both')),
                order_type=BybitFuturesOrderType(result.get('orderType')),
                status=BybitOrderStatus(result.get('orderStatus')),
                price=float(result.get('price', 0)),
                avg_price=float(result.get('avgPrice', 0)),
                qty=float(result.get('qty', 0)),
                cum_exec_qty=float(result.get('cumExecQty', 0)),
                cum_exec_value=float(result.get('cumExecValue', 0)),
                time_in_force=BybitFuturesTimeInForce(result.get('timeInForce', 'GTC')),
                stop_price=float(result.get('stopPrice')) if result.get('stopPrice') else None,
                reduce_only=result.get('reduceOnly', False),
                close_on_trigger=result.get('closeOnTrigger', False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            logger.info(f"Futures order placed: {order_response.order_id} for {request.symbol}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing futures order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel a futures order.
        
        Args:
            order_id: Order ID
            symbol: Symbol
            
        Returns:
            bool: Success indicator
        """
        try:
            data = {
                'symbol': symbol,
                'orderId': order_id
            }
            
            response = await self._request(
                method='POST',
                endpoint='/v5/order/cancel',
                data=data,
                signed=True
            )
            
            logger.info(f"Futures order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling futures order: {e}")
            return False

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_all_orders(self, symbol: str) -> bool:
        """
        Cancel all open orders for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            bool: Success indicator
        """
        try:
            data = {
                'symbol': symbol
            }
            
            response = await self._request(
                method='POST',
                endpoint='/v5/order/cancel-all',
                data=data,
                signed=True
            )
            
            logger.info(f"All futures orders cancelled for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return False

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """
        Get funding rate for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            Dict[str, Any]: Funding rate data
        """
        try:
            params = {
                'symbol': symbol
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/funding-rate',
                params=params
            )
            
            if response.get('list'):
                data = response['list'][0]
                return {
                    'symbol': symbol,
                    'funding_rate': float(data.get('fundingRate', 0)),
                    'funding_time': datetime.fromtimestamp(int(data.get('fundingTime', 0)) / 1000),
                    'next_funding_time': datetime.fromtimestamp(int(data.get('nextFundingTime', 0)) / 1000)
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting funding rate: {e}")
            return {}

    async def get_mark_price(self, symbol: str) -> Dict[str, Any]:
        """
        Get mark price for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            Dict[str, Any]: Mark price data
        """
        try:
            params = {
                'symbol': symbol
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/mark-price',
                params=params
            )
            
            if response.get('list'):
                data = response['list'][0]
                return {
                    'symbol': data.get('symbol'),
                    'mark_price': float(data.get('markPrice', 0)),
                    'index_price': float(data.get('indexPrice', 0)),
                    'last_funding_rate': float(data.get('lastFundingRate', 0)),
                    'timestamp': datetime.utcnow()
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting mark price: {e}")
            return {}

    # =========================================================================
    # Private Methods
    # =========================================================================

    async def _update_position_cache(self, symbol: str) -> None:
        """Update position cache"""
        try:
            positions = await self.get_positions(symbol)
            for pos in positions:
                self._position_cache[pos.symbol] = pos
        except Exception as e:
            logger.warning(f"Error updating position cache: {e}")

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Bybit futures connection"""
        await super().close()
        
        self._position_cache.clear()
        self._leverage_cache.clear()
        self._margin_mode_cache.clear()
        
        logger.info("BybitFutures closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/bybit/futures", tags=["Bybit Futures"])


async def get_futures(
    api_key: str = Query(..., description="Bybit API Key"),
    api_secret: str = Query(..., description="Bybit API Secret"),
    environment: BybitEnvironment = Query(BybitEnvironment.TESTNET),
    futures_type: BybitFuturesType = Query(BybitFuturesType.LINEAR)
) -> BybitFutures:
    """Dependency to get BybitFutures instance"""
    return BybitFutures(api_key, api_secret, environment, futures_type)


@router.get("/account")
async def get_account_info(
    futures: BybitFutures = Depends(get_futures)
):
    """Get futures account information"""
    return await futures.get_account_info()


@router.get("/positions")
async def get_positions(
    symbol: Optional[str] = Query(None),
    futures: BybitFutures = Depends(get_futures)
):
    """Get futures positions"""
    return await futures.get_positions(symbol)


@router.post("/leverage")
async def set_leverage(
    request: BybitFuturesLeverageRequest,
    futures: BybitFutures = Depends(get_futures)
):
    """Set leverage for a symbol"""
    return await futures.set_leverage(request.symbol, request.leverage, request.margin_mode)


@router.get("/leverage/{symbol}")
async def get_leverage(
    symbol: str,
    futures: BybitFutures = Depends(get_futures)
):
    """Get leverage for a symbol"""
    return await futures.get_leverage(symbol)


@router.post("/order")
async def place_order(
    request: BybitFuturesOrderRequest,
    futures: BybitFutures = Depends(get_futures)
):
    """Place a futures order"""
    return await futures.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    symbol: str = Query(..., description="Symbol"),
    futures: BybitFutures = Depends(get_futures)
):
    """Cancel a futures order"""
    success = await futures.cancel_order(order_id, symbol)
    return {"success": success}


@router.delete("/orders/{symbol}")
async def cancel_all_orders(
    symbol: str,
    futures: BybitFutures = Depends(get_futures)
):
    """Cancel all open orders for a symbol"""
    success = await futures.cancel_all_orders(symbol)
    return {"success": success}


@router.get("/funding-rate/{symbol}")
async def get_funding_rate(
    symbol: str,
    futures: BybitFutures = Depends(get_futures)
):
    """Get funding rate for a symbol"""
    return await futures.get_funding_rate(symbol)


@router.get("/mark-price/{symbol}")
async def get_mark_price(
    symbol: str,
    futures: BybitFutures = Depends(get_futures)
):
    """Get mark price for a symbol"""
    return await futures.get_mark_price(symbol)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitFutures',
    'BybitFuturesType',
    'BybitFuturesOrderType',
    'BybitFuturesOrderSide',
    'BybitFuturesPositionSide',
    'BybitFuturesTimeInForce',
    'BybitFuturesMarginMode',
    'BybitFuturesAccountInfo',
    'BybitFuturesPosition',
    'BybitFuturesOrderRequest',
    'BybitFuturesOrderResponse',
    'BybitFuturesLeverageRequest',
    'BybitFuturesStreamConfig',
    'router'
]
