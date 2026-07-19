"""
NEXUS AI TRADING SYSTEM - Coinbase Order Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/coinbase/order.py
Description: Coinbase order management with full API integration
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
from shared.constants.trading_constants import ORDER_TYPES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

# Coinbase imports
from trading.exchanges.coinbase.base import CoinbaseBase, CoinbaseEnvironment
from trading.exchanges.coinbase.account import (
    CoinbaseOrderRequest,
    CoinbaseOrderResponse,
    CoinbaseOrderSide,
    CoinbaseOrderType,
    CoinbaseOrderStatus,
    CoinbaseTimeInForce
)
from trading.exchanges.coinbase.exceptions import (
    CoinbaseException,
    CoinbaseOrderError,
    CoinbaseErrorCode,
    CoinbaseErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class CoinbaseOrderListStatus(str, Enum):
    """Coinbase order list status"""
    EXECUTING = "executing"
    ALL_DONE = "all_done"
    REJECTED = "rejected"


class CoinbaseOrderListType(str, Enum):
    """Coinbase order list types"""
    OCO = "oco"  # One Cancels Other
    BRACKET = "bracket"  # Bracket order


class CoinbaseStopDirection(str, Enum):
    """Coinbase stop direction"""
    UP = "up"
    DOWN = "down"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CoinbaseOCOOrderRequest(BaseModel):
    """Coinbase OCO order request"""
    product_id: str
    side: CoinbaseOrderSide
    size: float
    price: float  # Limit price
    stop_price: float  # Stop price
    stop_limit_price: Optional[float] = None
    stop_direction: CoinbaseStopDirection = CoinbaseStopDirection.DOWN
    time_in_force: CoinbaseTimeInForce = CoinbaseTimeInForce.GTC
    client_order_id: Optional[str] = None


class CoinbaseOCOOrderResponse(BaseModel):
    """Coinbase OCO order response"""
    order_id: str
    client_order_id: str
    product_id: str
    side: CoinbaseOrderSide
    type: str
    status: str
    price: float
    size: float
    filled_size: float
    stop_price: float
    stop_limit_price: Optional[float] = None
    time_in_force: CoinbaseTimeInForce
    created_at: datetime
    done_at: Optional[datetime] = None


class CoinbaseBracketOrderRequest(BaseModel):
    """Coinbase bracket order request"""
    product_id: str
    side: CoinbaseOrderSide
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    client_order_id: Optional[str] = None


class CoinbaseOrderHistoryRequest(BaseModel):
    """Coinbase order history request"""
    product_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 500
    status: Optional[CoinbaseOrderStatus] = None
    order_id: Optional[str] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CoinbaseOrderBookUpdate:
    """Coinbase order book update"""
    product_id: str
    order_id: str
    client_order_id: str
    price: float
    size: float
    filled_size: float
    status: str
    timestamp: datetime


# =============================================================================
# COINBASE ORDER
# =============================================================================

class CoinbaseOrder(CoinbaseBase):
    """
    Coinbase Order Management with full API integration.
    
    Features:
    - Place orders (market, limit, stop, stop-limit, OCO, bracket)
    - Cancel orders
    - Get order status
    - Order history
    - Open orders
    - Order lists
    - WebSocket order updates
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        environment: CoinbaseEnvironment = CoinbaseEnvironment.SANDBOX,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize CoinbaseOrder.
        
        Args:
            api_key: Coinbase API key
            api_secret: Coinbase API secret
            passphrase: Coinbase passphrase
            environment: Coinbase environment
            config: Exchange configuration
        """
        super().__init__(api_key, api_secret, passphrase, environment, config)
        
        # Error handler
        self._error_handler = CoinbaseErrorHandler()
        
        # Order cache
        self._order_cache: Dict[str, CoinbaseOrderResponse] = {}
        self._oco_order_cache: Dict[str, CoinbaseOCOOrderResponse] = {}
        
        # Order history
        self._order_history: List[CoinbaseOrderResponse] = []
        
        # WebSocket order streams
        self._order_streams: Dict[str, Any] = {}
        
        logger.info("CoinbaseOrder initialized")

    # =========================================================================
    # Place Orders
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: CoinbaseOrderRequest
    ) -> CoinbaseOrderResponse:
        """
        Place an order on Coinbase.
        
        Args:
            request: Order request
            
        Returns:
            CoinbaseOrderResponse: Order response
        """
        try:
            # Prepare order data
            data = {
                'product_id': request.product_id,
                'side': request.side.value,
                'type': request.order_type.value,
                'time_in_force': request.time_in_force.value,
                'post_only': request.post_only
            }
            
            if request.size:
                data['size'] = str(request.size)
            
            if request.funds:
                data['funds'] = str(request.funds)
            
            if request.price:
                data['price'] = str(request.price)
            
            if request.stop_price:
                data['stop_price'] = str(request.stop_price)
            
            if request.client_order_id:
                data['client_order_id'] = request.client_order_id
            
            if request.end_time:
                data['end_time'] = request.end_time.isoformat()
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/api/v3/brokerage/orders',
                data=data,
                signed=True
            )
            
            result = response
            
            # Parse response
            order_response = CoinbaseOrderResponse(
                order_id=result.get('order_id'),
                client_order_id=result.get('client_order_id'),
                product_id=result.get('product_id'),
                side=CoinbaseOrderSide(result.get('side')),
                order_type=CoinbaseOrderType(result.get('type')),
                status=CoinbaseOrderStatus(result.get('status')),
                price=float(result.get('price', 0)),
                filled_size=float(result.get('filled_size', 0)),
                size=float(result.get('size', 0)),
                funds=float(result.get('funds', 0)),
                filled_funds=float(result.get('filled_funds', 0)),
                time_in_force=CoinbaseTimeInForce(result.get('time_in_force', 'GTC')),
                stop_price=float(result.get('stop_price')) if result.get('stop_price') else None,
                post_only=result.get('post_only', False),
                created_at=datetime.utcnow(),
                done_at=None,
                done_reason=None
            )
            
            # Cache order
            self._order_cache[order_response.order_id] = order_response
            self._order_history.append(order_response)
            
            logger.info(f"Order placed: {order_response.order_id} for {request.product_id}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def place_oco_order(
        self,
        request: CoinbaseOCOOrderRequest
    ) -> CoinbaseOCOOrderResponse:
        """
        Place an OCO (One Cancels Other) order.
        
        Args:
            request: OCO order request
            
        Returns:
            CoinbaseOCOOrderResponse: OCO order response
        """
        try:
            # Prepare OCO data
            data = {
                'product_id': request.product_id,
                'side': request.side.value,
                'size': str(request.size),
                'price': str(request.price),
                'stop_price': str(request.stop_price),
                'stop_direction': request.stop_direction.value,
                'time_in_force': request.time_in_force.value
            }
            
            if request.stop_limit_price:
                data['stop_limit_price'] = str(request.stop_limit_price)
            
            if request.client_order_id:
                data['client_order_id'] = request.client_order_id
            
            # Place OCO order
            response = await self._request(
                method='POST',
                endpoint='/api/v3/brokerage/orders/oco',
                data=data,
                signed=True
            )
            
            result = response
            
            # Parse response
            oco_response = CoinbaseOCOOrderResponse(
                order_id=result.get('order_id'),
                client_order_id=result.get('client_order_id'),
                product_id=result.get('product_id'),
                side=CoinbaseOrderSide(result.get('side')),
                type=result.get('type', 'oco'),
                status=result.get('status', 'executing'),
                price=float(result.get('price', 0)),
                size=float(result.get('size', 0)),
                filled_size=float(result.get('filled_size', 0)),
                stop_price=float(result.get('stop_price', 0)),
                stop_limit_price=float(result.get('stop_limit_price')) if result.get('stop_limit_price') else None,
                time_in_force=CoinbaseTimeInForce(result.get('time_in_force', 'GTC')),
                created_at=datetime.utcnow(),
                done_at=None
            )
            
            # Cache
            self._oco_order_cache[oco_response.order_id] = oco_response
            
            logger.info(f"OCO order placed: {oco_response.order_id} for {request.product_id}")
            return oco_response
            
        except Exception as e:
            logger.error(f"Error placing OCO order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def place_bracket_order(
        self,
        request: CoinbaseBracketOrderRequest
    ) -> Dict[str, Any]:
        """
        Place a bracket order.
        
        Args:
            request: Bracket order request
            
        Returns:
            Dict[str, Any]: Bracket order response
        """
        try:
            # Place entry order
            entry_request = CoinbaseOrderRequest(
                product_id=request.product_id,
                side=request.side,
                order_type=CoinbaseOrderType.LIMIT,
                size=request.size,
                price=request.entry_price,
                client_order_id=request.client_order_id
            )
            
            entry_order = await self.place_order(entry_request)
            
            if entry_order.status != CoinbaseOrderStatus.OPEN:
                raise CoinbaseOrderError(
                    code=CoinbaseErrorCode.ORDER_REJECTED,
                    message=f"Entry order failed: {entry_order.status}"
                )
            
            # Place stop loss
            sl_request = CoinbaseOrderRequest(
                product_id=request.product_id,
                side=CoinbaseOrderSide.SELL if request.side == CoinbaseOrderSide.BUY else CoinbaseOrderSide.BUY,
                order_type=CoinbaseOrderType.STOP,
                size=request.size,
                stop_price=request.stop_loss,
                reduce_only=True
            )
            
            sl_order = await self.place_order(sl_request)
            
            # Place take profit
            tp_request = CoinbaseOrderRequest(
                product_id=request.product_id,
                side=CoinbaseOrderSide.SELL if request.side == CoinbaseOrderSide.BUY else CoinbaseOrderSide.BUY,
                order_type=CoinbaseOrderType.LIMIT,
                size=request.size,
                price=request.take_profit,
                reduce_only=True
            )
            
            tp_order = await self.place_order(tp_request)
            
            return {
                'entry_order': entry_order,
                'stop_loss': sl_order,
                'take_profit': tp_order,
                'product_id': request.product_id,
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error placing bracket order: {e}")
            raise

    # =========================================================================
    # Cancel Orders
    # =========================================================================

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
            response = await self._request(
                method='POST',
                endpoint=f'/api/v3/brokerage/orders/{order_id}/cancel',
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
    async def cancel_open_orders(self, product_id: Optional[str] = None) -> int:
        """
        Cancel all open orders.
        
        Args:
            product_id: Product ID (optional)
            
        Returns:
            int: Number of cancelled orders
        """
        try:
            params = {}
            if product_id:
                params['product_id'] = product_id
            
            response = await self._request(
                method='POST',
                endpoint='/api/v3/brokerage/orders/cancel',
                params=params,
                signed=True
            )
            
            cancelled_count = len(response.get('order_ids', []))
            
            # Clear cache for product
            if product_id:
                for order_id in list(self._order_cache.keys()):
                    if self._order_cache[order_id].product_id == product_id:
                        del self._order_cache[order_id]
            
            logger.info(f"Cancelled {cancelled_count} open orders")
            return cancelled_count
            
        except Exception as e:
            logger.error(f"Error cancelling open orders: {e}")
            return 0

    # =========================================================================
    # Get Orders
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order(self, order_id: str) -> Optional[CoinbaseOrderResponse]:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            
        Returns:
            Optional[CoinbaseOrderResponse]: Order details
        """
        try:
            # Check cache
            if order_id in self._order_cache:
                return self._order_cache[order_id]
            
            response = await self._request(
                method='GET',
                endpoint=f'/api/v3/brokerage/orders/{order_id}',
                signed=True
            )
            
            result = response
            
            order_response = CoinbaseOrderResponse(
                order_id=result.get('order_id'),
                client_order_id=result.get('client_order_id'),
                product_id=result.get('product_id'),
                side=CoinbaseOrderSide(result.get('side')),
                order_type=CoinbaseOrderType(result.get('type')),
                status=CoinbaseOrderStatus(result.get('status')),
                price=float(result.get('price', 0)),
                filled_size=float(result.get('filled_size', 0)),
                size=float(result.get('size', 0)),
                funds=float(result.get('funds', 0)),
                filled_funds=float(result.get('filled_funds', 0)),
                time_in_force=CoinbaseTimeInForce(result.get('time_in_force', 'GTC')),
                stop_price=float(result.get('stop_price')) if result.get('stop_price') else None,
                post_only=result.get('post_only', False),
                created_at=datetime.utcnow(),
                done_at=None,
                done_reason=None
            )
            
            # Cache
            self._order_cache[order_response.order_id] = order_response
            
            return order_response
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    @retry_async(max_attempts=3, delay=0.5)
    async def get_open_orders(self, product_id: Optional[str] = None) -> List[CoinbaseOrderResponse]:
        """
        Get open orders.
        
        Args:
            product_id: Product ID (optional)
            
        Returns:
            List[CoinbaseOrderResponse]: Open orders
        """
        try:
            params = {}
            if product_id:
                params['product_id'] = product_id
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/brokerage/orders/open',
                params=params,
                signed=True
            )
            
            orders = []
            for data in response.get('orders', []):
                order_response = CoinbaseOrderResponse(
                    order_id=data.get('order_id'),
                    client_order_id=data.get('client_order_id'),
                    product_id=data.get('product_id'),
                    side=CoinbaseOrderSide(data.get('side')),
                    order_type=CoinbaseOrderType(data.get('type')),
                    status=CoinbaseOrderStatus(data.get('status')),
                    price=float(data.get('price', 0)),
                    filled_size=float(data.get('filled_size', 0)),
                    size=float(data.get('size', 0)),
                    funds=float(data.get('funds', 0)),
                    filled_funds=float(data.get('filled_funds', 0)),
                    time_in_force=CoinbaseTimeInForce(data.get('time_in_force', 'GTC')),
                    stop_price=float(data.get('stop_price')) if data.get('stop_price') else None,
                    post_only=data.get('post_only', False),
                    created_at=datetime.utcnow(),
                    done_at=None,
                    done_reason=None
                )
                orders.append(order_response)
                self._order_cache[order_response.order_id] = order_response
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order_history(
        self,
        request: CoinbaseOrderHistoryRequest
    ) -> List[CoinbaseOrderResponse]:
        """
        Get order history.
        
        Args:
            request: Order history request
            
        Returns:
            List[CoinbaseOrderResponse]: Order history
        """
        try:
            params = {'limit': request.limit}
            
            if request.product_id:
                params['product_id'] = request.product_id
            
            if request.start_date:
                params['start_date'] = request.start_date.isoformat()
            
            if request.end_date:
                params['end_date'] = request.end_date.isoformat()
            
            if request.status:
                params['status'] = request.status.value
            
            if request.order_id:
                params['order_id'] = request.order_id
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/brokerage/orders/history',
                params=params,
                signed=True
            )
            
            orders = []
            for data in response.get('orders', []):
                order_response = CoinbaseOrderResponse(
                    order_id=data.get('order_id'),
                    client_order_id=data.get('client_order_id'),
                    product_id=data.get('product_id'),
                    side=CoinbaseOrderSide(data.get('side')),
                    order_type=CoinbaseOrderType(data.get('type')),
                    status=CoinbaseOrderStatus(data.get('status')),
                    price=float(data.get('price', 0)),
                    filled_size=float(data.get('filled_size', 0)),
                    size=float(data.get('size', 0)),
                    funds=float(data.get('funds', 0)),
                    filled_funds=float(data.get('filled_funds', 0)),
                    time_in_force=CoinbaseTimeInForce(data.get('time_in_force', 'GTC')),
                    stop_price=float(data.get('stop_price')) if data.get('stop_price') else None,
                    post_only=data.get('post_only', False),
                    created_at=datetime.utcnow(),
                    done_at=None,
                    done_reason=None
                )
                orders.append(order_response)
            
            # Update history
            self._order_history.extend(orders)
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting order history: {e}")
            return []

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _parse_order_response(self, data: Dict[str, Any]) -> CoinbaseOrderResponse:
        """Parse order response"""
        return CoinbaseOrderResponse(
            order_id=data.get('order_id'),
            client_order_id=data.get('client_order_id'),
            product_id=data.get('product_id'),
            side=CoinbaseOrderSide(data.get('side')),
            order_type=CoinbaseOrderType(data.get('type')),
            status=CoinbaseOrderStatus(data.get('status')),
            price=float(data.get('price', 0)),
            filled_size=float(data.get('filled_size', 0)),
            size=float(data.get('size', 0)),
            funds=float(data.get('funds', 0)),
            filled_funds=float(data.get('filled_funds', 0)),
            time_in_force=CoinbaseTimeInForce(data.get('time_in_force', 'GTC')),
            stop_price=float(data.get('stop_price')) if data.get('stop_price') else None,
            post_only=data.get('post_only', False),
            created_at=datetime.utcnow(),
            done_at=None,
            done_reason=None
        )

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Coinbase order module"""
        # Close WebSocket streams
        for stream_key in list(self._order_streams.keys()):
            await self.unsubscribe_order_stream(stream_key)
        
        await super().close()
        
        self._order_cache.clear()
        self._oco_order_cache.clear()
        self._order_history.clear()
        
        logger.info("CoinbaseOrder closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/coinbase/order", tags=["Coinbase Order"])


async def get_order(
    api_key: str = Query(..., description="Coinbase API Key"),
    api_secret: str = Query(..., description="Coinbase API Secret"),
    passphrase: str = Query(..., description="Coinbase Passphrase"),
    environment: CoinbaseEnvironment = Query(CoinbaseEnvironment.SANDBOX)
) -> CoinbaseOrder:
    """Dependency to get CoinbaseOrder instance"""
    return CoinbaseOrder(api_key, api_secret, passphrase, environment)


@router.post("/place")
async def place_order(
    request: CoinbaseOrderRequest,
    order: CoinbaseOrder = Depends(get_order)
):
    """Place an order"""
    return await order.place_order(request)


@router.post("/place/oco")
async def place_oco_order(
    request: CoinbaseOCOOrderRequest,
    order: CoinbaseOrder = Depends(get_order)
):
    """Place an OCO order"""
    return await order.place_oco_order(request)


@router.post("/place/bracket")
async def place_bracket_order(
    request: CoinbaseBracketOrderRequest,
    order: CoinbaseOrder = Depends(get_order)
):
    """Place a bracket order"""
    return await order.place_bracket_order(request)


@router.delete("/{order_id}")
async def cancel_order(
    order_id: str,
    order: CoinbaseOrder = Depends(get_order)
):
    """Cancel an order"""
    success = await order.cancel_order(order_id)
    return {"success": success}


@router.delete("/open")
async def cancel_open_orders(
    product_id: Optional[str] = Query(None),
    order: CoinbaseOrder = Depends(get_order)
):
    """Cancel all open orders"""
    count = await order.cancel_open_orders(product_id)
    return {"cancelled": count}


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    order: CoinbaseOrder = Depends(get_order)
):
    """Get order details"""
    return await order.get_order(order_id)


@router.get("/open")
async def get_open_orders(
    product_id: Optional[str] = Query(None),
    order: CoinbaseOrder = Depends(get_order)
):
    """Get open orders"""
    return await order.get_open_orders(product_id)


@router.post("/history")
async def get_order_history(
    request: CoinbaseOrderHistoryRequest,
    order: CoinbaseOrder = Depends(get_order)
):
    """Get order history"""
    return await order.get_order_history(request)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CoinbaseOrder',
    'CoinbaseOrderListStatus',
    'CoinbaseOrderListType',
    'CoinbaseStopDirection',
    'CoinbaseOCOOrderRequest',
    'CoinbaseOCOOrderResponse',
    'CoinbaseBracketOrderRequest',
    'CoinbaseOrderHistoryRequest',
    'CoinbaseOrderBookUpdate',
    'router'
]
