"""
NEXUS AI TRADING SYSTEM - Bybit Inverse Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/inverse.py
Description: Bybit inverse futures trading with full API integration
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
from trading.exchanges.bybit.futures import (
    BybitFutures,
    BybitFuturesType,
    BybitFuturesPosition,
    BybitFuturesOrderRequest,
    BybitFuturesOrderResponse,
    BybitFuturesPositionSide,
    BybitFuturesLeverageRequest,
    BybitFuturesMarginMode
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

class BybitInverseOrderType(str, Enum):
    """Bybit inverse order types"""
    LIMIT = "Limit"
    MARKET = "Market"
    STOP = "Stop"
    STOP_LIMIT = "StopLimit"
    TAKE_PROFIT = "TakeProfit"
    TAKE_PROFIT_LIMIT = "TakeProfitLimit"
    TRAILING_STOP = "TrailingStop"


class BybitInverseOrderSide(str, Enum):
    """Bybit inverse order sides"""
    BUY = "Buy"
    SELL = "Sell"


class BybitInversePositionSide(str, Enum):
    """Bybit inverse position sides"""
    BOTH = "Both"
    LONG = "Long"
    SHORT = "Short"


class BybitInverseTimeInForce(str, Enum):
    """Bybit inverse time in force"""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "PostOnly"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BybitInverseAccountInfo(BaseModel):
    """Bybit inverse account information"""
    account_id: str
    account_type: str
    total_equity: float
    available_balance: float
    used_margin: float
    margin_ratio: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class BybitInversePosition(BaseModel):
    """Bybit inverse position"""
    symbol: str
    position_side: BybitInversePositionSide
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


class BybitInverseOrderRequest(BaseModel):
    """Bybit inverse order request"""
    symbol: str
    side: BybitInverseOrderSide
    position_side: BybitInversePositionSide = BybitInversePositionSide.BOTH
    order_type: BybitInverseOrderType = BybitInverseOrderType.LIMIT
    qty: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: BybitInverseTimeInForce = BybitInverseTimeInForce.GTC
    reduce_only: bool = False
    close_on_trigger: bool = False
    position_idx: int = 0
    order_link_id: Optional[str] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    tp_trigger_by: Optional[str] = None
    sl_trigger_by: Optional[str] = None
    tpsl_mode: str = "Full"


class BybitInverseOrderResponse(BaseModel):
    """Bybit inverse order response"""
    order_id: str
    order_link_id: str
    symbol: str
    side: BybitInverseOrderSide
    position_side: BybitInversePositionSide
    order_type: BybitInverseOrderType
    status: BybitOrderStatus
    price: float
    avg_price: float
    qty: float
    cum_exec_qty: float
    cum_exec_value: float
    time_in_force: BybitInverseTimeInForce
    stop_price: Optional[float] = None
    reduce_only: bool
    close_on_trigger: bool
    created_at: datetime
    updated_at: datetime


class BybitInverseLeverageRequest(BaseModel):
    """Bybit inverse leverage request"""
    symbol: str
    leverage: int = 1
    margin_mode: BybitFuturesMarginMode = BybitFuturesMarginMode.ISOLATED


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BybitInverseStreamConfig:
    """Bybit inverse stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BYBIT INVERSE
# =============================================================================

class BybitInverse(BybitBase):
    """
    Bybit Inverse Futures Trading with full API integration.
    
    Features:
    - Inverse futures trading
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
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BybitInverse.
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            environment: Bybit environment
            config: Exchange configuration
        """
        super().__init__(
            api_key,
            api_secret,
            environment,
            BybitCategory.INVERSE,
            config
        )
        
        # Error handler
        self._error_handler = BybitErrorHandler()
        
        # Position cache
        self._position_cache: Dict[str, BybitInversePosition] = {}
        
        # Leverage cache
        self._leverage_cache: Dict[str, int] = {}
        
        # Margin mode cache
        self._margin_mode_cache: Dict[str, str] = {}
        
        logger.info("BybitInverse initialized")

    # =========================================================================
    # Account Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_account_info(self) -> BybitInverseAccountInfo:
        """
        Get inverse account information.
        
        Returns:
            BybitInverseAccountInfo: Account information
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/v5/account/info',
                signed=True
            )
            
            data = response
            
            return BybitInverseAccountInfo(
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
            logger.error(f"Error getting inverse account info: {e}")
            raise

    # =========================================================================
    # Position Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_positions(self, symbol: Optional[str] = None) -> List[BybitInversePosition]:
        """
        Get inverse positions.
        
        Args:
            symbol: Symbol (optional)
            
        Returns:
            List[BybitInversePosition]: Positions
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
                position = BybitInversePosition(
                    symbol=data.get('symbol'),
                    position_side=BybitInversePositionSide(data.get('side', 'Both')),
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
            logger.error(f"Error getting inverse positions: {e}")
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
        request: BybitInverseOrderRequest
    ) -> BybitInverseOrderResponse:
        """
        Place an inverse order.
        
        Args:
            request: Order request
            
        Returns:
            BybitInverseOrderResponse: Order response
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
            order_response = BybitInverseOrderResponse(
                order_id=result.get('orderId'),
                order_link_id=result.get('orderLinkId', ''),
                symbol=result.get('symbol'),
                side=BybitInverseOrderSide(result.get('side')),
                position_side=BybitInversePositionSide(result.get('positionSide', 'Both')),
                order_type=BybitInverseOrderType(result.get('orderType')),
                status=BybitOrderStatus(result.get('orderStatus')),
                price=float(result.get('price', 0)),
                avg_price=float(result.get('avgPrice', 0)),
                qty=float(result.get('qty', 0)),
                cum_exec_qty=float(result.get('cumExecQty', 0)),
                cum_exec_value=float(result.get('cumExecValue', 0)),
                time_in_force=BybitInverseTimeInForce(result.get('timeInForce', 'GTC')),
                stop_price=float(result.get('stopPrice')) if result.get('stopPrice') else None,
                reduce_only=result.get('reduceOnly', False),
                close_on_trigger=result.get('closeOnTrigger', False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            logger.info(f"Inverse order placed: {order_response.order_id} for {request.symbol}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing inverse order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an inverse order.
        
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
            
            logger.info(f"Inverse order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling inverse order: {e}")
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
            
            logger.info(f"All inverse orders cancelled for {symbol}")
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
        """Close the Bybit inverse connection"""
        await super().close()
        
        self._position_cache.clear()
        self._leverage_cache.clear()
        self._margin_mode_cache.clear()
        
        logger.info("BybitInverse closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/bybit/inverse", tags=["Bybit Inverse"])


async def get_inverse(
    api_key: str = Query(..., description="Bybit API Key"),
    api_secret: str = Query(..., description="Bybit API Secret"),
    environment: BybitEnvironment = Query(BybitEnvironment.TESTNET)
) -> BybitInverse:
    """Dependency to get BybitInverse instance"""
    return BybitInverse(api_key, api_secret, environment)


@router.get("/account")
async def get_account_info(
    inverse: BybitInverse = Depends(get_inverse)
):
    """Get inverse account information"""
    return await inverse.get_account_info()


@router.get("/positions")
async def get_positions(
    symbol: Optional[str] = Query(None),
    inverse: BybitInverse = Depends(get_inverse)
):
    """Get inverse positions"""
    return await inverse.get_positions(symbol)


@router.post("/leverage")
async def set_leverage(
    request: BybitInverseLeverageRequest,
    inverse: BybitInverse = Depends(get_inverse)
):
    """Set leverage for a symbol"""
    return await inverse.set_leverage(request.symbol, request.leverage, request.margin_mode)


@router.get("/leverage/{symbol}")
async def get_leverage(
    symbol: str,
    inverse: BybitInverse = Depends(get_inverse)
):
    """Get leverage for a symbol"""
    return await inverse.get_leverage(symbol)


@router.post("/order")
async def place_order(
    request: BybitInverseOrderRequest,
    inverse: BybitInverse = Depends(get_inverse)
):
    """Place an inverse order"""
    return await inverse.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    symbol: str = Query(..., description="Symbol"),
    inverse: BybitInverse = Depends(get_inverse)
):
    """Cancel an inverse order"""
    success = await inverse.cancel_order(order_id, symbol)
    return {"success": success}


@router.delete("/orders/{symbol}")
async def cancel_all_orders(
    symbol: str,
    inverse: BybitInverse = Depends(get_inverse)
):
    """Cancel all open orders for a symbol"""
    success = await inverse.cancel_all_orders(symbol)
    return {"success": success}


@router.get("/funding-rate/{symbol}")
async def get_funding_rate(
    symbol: str,
    inverse: BybitInverse = Depends(get_inverse)
):
    """Get funding rate for a symbol"""
    return await inverse.get_funding_rate(symbol)


@router.get("/mark-price/{symbol}")
async def get_mark_price(
    symbol: str,
    inverse: BybitInverse = Depends(get_inverse)
):
    """Get mark price for a symbol"""
    return await inverse.get_mark_price(symbol)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitInverse',
    'BybitInverseOrderType',
    'BybitInverseOrderSide',
    'BybitInversePositionSide',
    'BybitInverseTimeInForce',
    'BybitInverseAccountInfo',
    'BybitInversePosition',
    'BybitInverseOrderRequest',
    'BybitInverseOrderResponse',
    'BybitInverseLeverageRequest',
    'BybitInverseStreamConfig',
    'router'
]
