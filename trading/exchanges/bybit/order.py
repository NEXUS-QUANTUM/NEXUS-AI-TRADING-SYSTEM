"""
NEXUS AI TRADING SYSTEM - Bybit Order Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/order.py
Description: Bybit order management with full API integration
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
from shared.constants.trading_constants import ORDER_TYPES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

# Bybit imports
from trading.exchanges.bybit.base import BybitBase, BybitEnvironment, BybitCategory
from trading.exchanges.bybit.account import (
    BybitOrderRequest,
    BybitOrderResponse,
    BybitOrderSide,
    BybitOrderType,
    BybitOrderStatus,
    BybitTimeInForce
)
from trading.exchanges.bybit.exceptions import (
    BybitException,
    BybitOrderError,
    BybitErrorCode,
    BybitErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BybitOrderListStatus(str, Enum):
    """Bybit order list status"""
    EXECUTING = "Executing"
    ALL_DONE = "AllDone"
    REJECTED = "Rejected"


class BybitOrderListType(str, Enum):
    """Bybit order list types"""
    OCO = "OCO"  # One Cancels Other
    BRACKET = "Bracket"  # Bracket order


class BybitTriggerBy(str, Enum):
    """Bybit trigger by"""
    PRICE = "Price"
    INDEX_PRICE = "IndexPrice"
    MARK_PRICE = "MarkPrice"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BybitOCOOrderRequest(BaseModel):
    """Bybit OCO order request"""
    symbol: str
    side: BybitOrderSide
    qty: float
    price: float  # Limit price
    stop_price: float  # Stop price
    stop_limit_price: Optional[float] = None
    stop_time_in_force: BybitTimeInForce = BybitTimeInForce.GTC
    limit_time_in_force: BybitTimeInForce = BybitTimeInForce.GTC
    order_link_id: Optional[str] = None
    tpsl_mode: str = "Full"


class BybitOCOOrderResponse(BaseModel):
    """Bybit OCO order response"""
    order_list_id: str
    contingency_type: str
    list_status_type: str
    list_order_status: BybitOrderListStatus
    order_ids: List[str]
    orders: List[BybitOrderResponse]
    order_link_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BybitBracketOrderRequest(BaseModel):
    """Bybit bracket order request"""
    symbol: str
    side: BybitOrderSide
    qty: float
    entry_price: float
    stop_loss: float
    take_profit: float
    sl_trigger_by: BybitTriggerBy = BybitTriggerBy.MARK_PRICE
    tp_trigger_by: BybitTriggerBy = BybitTriggerBy.MARK_PRICE
    order_link_id: Optional[str] = None


class BybitOrderHistoryRequest(BaseModel):
    """Bybit order history request"""
    symbol: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 500
    order_id: Optional[str] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BybitOrderBookUpdate:
    """Bybit order book update"""
    symbol: str
    order_id: str
    order_link_id: str
    price: float
    qty: float
    executed_qty: float
    status: str
    timestamp: datetime


# =============================================================================
# BYBIT ORDER
# =============================================================================

class BybitOrder(BybitBase):
    """
    Bybit Order Management with full API integration.
    
    Features:
    - Place orders (limit, market, stop, stop-limit, OCO, bracket)
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
        environment: BybitEnvironment = BybitEnvironment.TESTNET,
        category: BybitCategory = BybitCategory.LINEAR,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BybitOrder.
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            environment: Bybit environment
            category: Bybit category
            config: Exchange configuration
        """
        super().__init__(api_key, api_secret, environment, category, config)
        
        # Error handler
        self._error_handler = BybitErrorHandler()
        
        # Order cache
        self._order_cache: Dict[str, BybitOrderResponse] = {}
        self._oco_order_cache: Dict[str, BybitOCOOrderResponse] = {}
        
        # Order history
        self._order_history: List[BybitOrderResponse] = []
        
        # WebSocket order streams
        self._order_streams: Dict[str, Any] = {}
        
        logger.info(f"BybitOrder initialized for {category.value}")

    # =========================================================================
    # Place Orders
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: BybitOrderRequest
    ) -> BybitOrderResponse:
        """
        Place an order on Bybit.
        
        Args:
            request: Order request
            
        Returns:
            BybitOrderResponse: Order response
        """
        try:
            # Prepare order data
            data = {
                'symbol': request.symbol,
                'side': request.side.value,
                'orderType': request.order_type.value,
                'qty': str(request.qty),
                'timeInForce': request.time_in_force.value
            }
            
            if request.price:
                data['price'] = str(request.price)
            
            if request.stop_price:
                data['stopPrice'] = str(request.stop_price)
            
            if request.reduce_only:
                data['reduceOnly'] = True
            
            if request.close_on_trigger:
                data['closeOnTrigger'] = True
            
            if request.position_idx:
                data['positionIdx'] = request.position_idx
            
            if request.order_link_id:
                data['orderLinkId'] = request.order_link_id
            
            if request.take_profit:
                data['takeProfit'] = str(request.take_profit)
            
            if request.stop_loss:
                data['stopLoss'] = str(request.stop_loss)
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/v5/order/create',
                data=data,
                signed=True
            )
            
            result = response
            
            # Parse response
            order_response = BybitOrderResponse(
                order_id=result.get('orderId'),
                order_link_id=result.get('orderLinkId', ''),
                symbol=result.get('symbol'),
                side=BybitOrderSide(result.get('side')),
                order_type=BybitOrderType(result.get('orderType')),
                status=BybitOrderStatus(result.get('orderStatus')),
                price=float(result.get('price', 0)),
                avg_price=float(result.get('avgPrice', 0)),
                qty=float(result.get('qty', 0)),
                cum_exec_qty=float(result.get('cumExecQty', 0)),
                cum_exec_value=float(result.get('cumExecValue', 0)),
                time_in_force=BybitTimeInForce(result.get('timeInForce', 'GTC')),
                stop_price=float(result.get('stopPrice')) if result.get('stopPrice') else None,
                reduce_only=result.get('reduceOnly', False),
                close_on_trigger=result.get('closeOnTrigger', False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Cache order
            self._order_cache[order_response.order_id] = order_response
            self._order_history.append(order_response)
            
            logger.info(f"Order placed: {order_response.order_id} for {request.symbol}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def place_oco_order(
        self,
        request: BybitOCOOrderRequest
    ) -> BybitOCOOrderResponse:
        """
        Place an OCO (One Cancels Other) order.
        
        Args:
            request: OCO order request
            
        Returns:
            BybitOCOOrderResponse: OCO order response
        """
        try:
            # Prepare OCO data
            data = {
                'symbol': request.symbol,
                'side': request.side.value,
                'qty': str(request.qty),
                'price': str(request.price),
                'stopPrice': str(request.stop_price),
                'tpslMode': request.tpsl_mode
            }
            
            if request.stop_limit_price:
                data['stopLimitPrice'] = str(request.stop_limit_price)
            
            if request.stop_time_in_force:
                data['stopTimeInForce'] = request.stop_time_in_force.value
            
            if request.limit_time_in_force:
                data['limitTimeInForce'] = request.limit_time_in_force.value
            
            if request.order_link_id:
                data['orderLinkId'] = request.order_link_id
            
            # Place OCO order
            response = await self._request(
                method='POST',
                endpoint='/v5/order/oco',
                data=data,
                signed=True
            )
            
            result = response
            
            # Parse response
            oco_response = BybitOCOOrderResponse(
                order_list_id=result.get('orderListId'),
                contingency_type=result.get('contingencyType', 'OCO'),
                list_status_type=result.get('listStatusType', 'Executing'),
                list_order_status=BybitOrderListStatus(result.get('listOrderStatus', 'Executing')),
                order_ids=result.get('orderIds', []),
                orders=[],  # Would parse orders if needed
                order_link_id=result.get('orderLinkId'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Cache
            self._oco_order_cache[oco_response.order_list_id] = oco_response
            
            logger.info(f"OCO order placed: {oco_response.order_list_id} for {request.symbol}")
            return oco_response
            
        except Exception as e:
            logger.error(f"Error placing OCO order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def place_bracket_order(
        self,
        request: BybitBracketOrderRequest
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
            entry_request = BybitOrderRequest(
                symbol=request.symbol,
                side=request.side,
                order_type=BybitOrderType.LIMIT,
                qty=request.qty,
                price=request.entry_price,
                order_link_id=request.order_link_id
            )
            
            entry_order = await self.place_order(entry_request)
            
            if entry_order.status != BybitOrderStatus.NEW:
                raise BybitOrderError(
                    code=BybitErrorCode.ORDER_REJECTED,
                    message=f"Entry order failed: {entry_order.status}"
                )
            
            # Place stop loss
            sl_request = BybitOrderRequest(
                symbol=request.symbol,
                side=BybitOrderSide.SELL if request.side == BybitOrderSide.BUY else BybitOrderSide.BUY,
                order_type=BybitOrderType.STOP,
                qty=request.qty,
                stop_price=request.stop_loss,
                reduce_only=True
            )
            
            sl_order = await self.place_order(sl_request)
            
            # Place take profit
            tp_request = BybitOrderRequest(
                symbol=request.symbol,
                side=BybitOrderSide.SELL if request.side == BybitOrderSide.BUY else BybitOrderSide.BUY,
                order_type=BybitOrderType.TAKE_PROFIT,
                qty=request.qty,
                price=request.take_profit,
                reduce_only=True
            )
            
            tp_order = await self.place_order(tp_request)
            
            return {
                'entry_order': entry_order,
                'stop_loss': sl_order,
                'take_profit': tp_order,
                'symbol': request.symbol,
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error placing bracket order: {e}")
            raise

    # =========================================================================
    # Cancel Orders
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order.
        
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
            
            # Remove from cache
            if order_id in self._order_cache:
                del self._order_cache[order_id]
            
            logger.info(f"Order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_open_orders(self, symbol: str) -> int:
        """
        Cancel all open orders for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            int: Number of cancelled orders
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
            
            cancelled_count = len(response.get('list', []))
            
            # Clear cache for symbol
            for order_id in list(self._order_cache.keys()):
                if self._order_cache[order_id].symbol == symbol:
                    del self._order_cache[order_id]
            
            logger.info(f"Cancelled {cancelled_count} open orders for {symbol}")
            return cancelled_count
            
        except Exception as e:
            logger.error(f"Error cancelling open orders for {symbol}: {e}")
            return 0

    # =========================================================================
    # Get Orders
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order(self, order_id: str, symbol: str) -> Optional[BybitOrderResponse]:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            symbol: Symbol
            
        Returns:
            Optional[BybitOrderResponse]: Order details
        """
        try:
            # Check cache
            if order_id in self._order_cache:
                return self._order_cache[order_id]
            
            params = {
                'symbol': symbol,
                'orderId': order_id
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/order',
                params=params,
                signed=True
            )
            
            result = response
            
            order_response = BybitOrderResponse(
                order_id=result.get('orderId'),
                order_link_id=result.get('orderLinkId', ''),
                symbol=result.get('symbol'),
                side=BybitOrderSide(result.get('side')),
                order_type=BybitOrderType(result.get('orderType')),
                status=BybitOrderStatus(result.get('orderStatus')),
                price=float(result.get('price', 0)),
                avg_price=float(result.get('avgPrice', 0)),
                qty=float(result.get('qty', 0)),
                cum_exec_qty=float(result.get('cumExecQty', 0)),
                cum_exec_value=float(result.get('cumExecValue', 0)),
                time_in_force=BybitTimeInForce(result.get('timeInForce', 'GTC')),
                stop_price=float(result.get('stopPrice')) if result.get('stopPrice') else None,
                reduce_only=result.get('reduceOnly', False),
                close_on_trigger=result.get('closeOnTrigger', False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Cache
            self._order_cache[order_response.order_id] = order_response
            
            return order_response
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    @retry_async(max_attempts=3, delay=0.5)
    async def get_open_orders(self, symbol: str) -> List[BybitOrderResponse]:
        """
        Get open orders for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            List[BybitOrderResponse]: Open orders
        """
        try:
            params = {
                'symbol': symbol
            }
            
            response = await self._request(
                method='GET',
                endpoint='/v5/order/open-orders',
                params=params,
                signed=True
            )
            
            orders = []
            for data in response.get('list', []):
                order_response = BybitOrderResponse(
                    order_id=data.get('orderId'),
                    order_link_id=data.get('orderLinkId', ''),
                    symbol=data.get('symbol'),
                    side=BybitOrderSide(data.get('side')),
                    order_type=BybitOrderType(data.get('orderType')),
                    status=BybitOrderStatus(data.get('orderStatus')),
                    price=float(data.get('price', 0)),
                    avg_price=float(data.get('avgPrice', 0)),
                    qty=float(data.get('qty', 0)),
                    cum_exec_qty=float(data.get('cumExecQty', 0)),
                    cum_exec_value=float(data.get('cumExecValue', 0)),
                    time_in_force=BybitTimeInForce(data.get('timeInForce', 'GTC')),
                    stop_price=float(data.get('stopPrice')) if data.get('stopPrice') else None,
                    reduce_only=data.get('reduceOnly', False),
                    close_on_trigger=data.get('closeOnTrigger', False),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                orders.append(order_response)
                self._order_cache[order_response.order_id] = order_response
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting open orders for {symbol}: {e}")
            return []

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order_history(
        self,
        request: BybitOrderHistoryRequest
    ) -> List[BybitOrderResponse]:
        """
        Get order history.
        
        Args:
            request: Order history request
            
        Returns:
            List[BybitOrderResponse]: Order history
        """
        try:
            params = {
                'symbol': request.symbol,
                'limit': request.limit
            }
            
            if request.start_time:
                params['startTime'] = int(request.start_time.timestamp() * 1000)
            
            if request.end_time:
                params['endTime'] = int(request.end_time.timestamp() * 1000)
            
            if request.order_id:
                params['orderId'] = request.order_id
            
            response = await self._request(
                method='GET',
                endpoint='/v5/order/history',
                params=params,
                signed=True
            )
            
            orders = []
            for data in response.get('list', []):
                order_response = BybitOrderResponse(
                    order_id=data.get('orderId'),
                    order_link_id=data.get('orderLinkId', ''),
                    symbol=data.get('symbol'),
                    side=BybitOrderSide(data.get('side')),
                    order_type=BybitOrderType(data.get('orderType')),
                    status=BybitOrderStatus(data.get('orderStatus')),
                    price=float(data.get('price', 0)),
                    avg_price=float(data.get('avgPrice', 0)),
                    qty=float(data.get('qty', 0)),
                    cum_exec_qty=float(data.get('cumExecQty', 0)),
                    cum_exec_value=float(data.get('cumExecValue', 0)),
                    time_in_force=BybitTimeInForce(data.get('timeInForce', 'GTC')),
                    stop_price=float(data.get('stopPrice')) if data.get('stopPrice') else None,
                    reduce_only=data.get('reduceOnly', False),
                    close_on_trigger=data.get('closeOnTrigger', False),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
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

    def _parse_order_response(self, data: Dict[str, Any]) -> BybitOrderResponse:
        """Parse order response"""
        return BybitOrderResponse(
            order_id=data.get('orderId'),
            order_link_id=data.get('orderLinkId', ''),
            symbol=data.get('symbol'),
            side=BybitOrderSide(data.get('side')),
            order_type=BybitOrderType(data.get('orderType')),
            status=BybitOrderStatus(data.get('orderStatus')),
            price=float(data.get('price', 0)),
            avg_price=float(data.get('avgPrice', 0)),
            qty=float(data.get('qty', 0)),
            cum_exec_qty=float(data.get('cumExecQty', 0)),
            cum_exec_value=float(data.get('cumExecValue', 0)),
            time_in_force=BybitTimeInForce(data.get('timeInForce', 'GTC')),
            stop_price=float(data.get('stopPrice')) if data.get('stopPrice') else None,
            reduce_only=data.get('reduceOnly', False),
            close_on_trigger=data.get('closeOnTrigger', False),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Bybit order module"""
        await super().close()
        
        self._order_cache.clear()
        self._oco_order_cache.clear()
        self._order_history.clear()
        
        logger.info("BybitOrder closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/bybit/order", tags=["Bybit Order"])


async def get_order(
    api_key: str = Query(..., description="Bybit API Key"),
    api_secret: str = Query(..., description="Bybit API Secret"),
    environment: BybitEnvironment = Query(BybitEnvironment.TESTNET),
    category: BybitCategory = Query(BybitCategory.LINEAR)
) -> BybitOrder:
    """Dependency to get BybitOrder instance"""
    return BybitOrder(api_key, api_secret, environment, category)


@router.post("/place")
async def place_order(
    request: BybitOrderRequest,
    order: BybitOrder = Depends(get_order)
):
    """Place an order"""
    return await order.place_order(request)


@router.post("/place/oco")
async def place_oco_order(
    request: BybitOCOOrderRequest,
    order: BybitOrder = Depends(get_order)
):
    """Place an OCO order"""
    return await order.place_oco_order(request)


@router.post("/place/bracket")
async def place_bracket_order(
    request: BybitBracketOrderRequest,
    order: BybitOrder = Depends(get_order)
):
    """Place a bracket order"""
    return await order.place_bracket_order(request)


@router.delete("/{order_id}")
async def cancel_order(
    order_id: str,
    symbol: str = Query(..., description="Symbol"),
    order: BybitOrder = Depends(get_order)
):
    """Cancel an order"""
    success = await order.cancel_order(order_id, symbol)
    return {"success": success}


@router.delete("/open/{symbol}")
async def cancel_open_orders(
    symbol: str,
    order: BybitOrder = Depends(get_order)
):
    """Cancel all open orders for a symbol"""
    count = await order.cancel_open_orders(symbol)
    return {"cancelled": count}


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    symbol: str = Query(..., description="Symbol"),
    order: BybitOrder = Depends(get_order)
):
    """Get order details"""
    return await order.get_order(order_id, symbol)


@router.get("/open/{symbol}")
async def get_open_orders(
    symbol: str,
    order: BybitOrder = Depends(get_order)
):
    """Get open orders for a symbol"""
    return await order.get_open_orders(symbol)


@router.post("/history")
async def get_order_history(
    request: BybitOrderHistoryRequest,
    order: BybitOrder = Depends(get_order)
):
    """Get order history"""
    return await order.get_order_history(request)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitOrder',
    'BybitOrderListStatus',
    'BybitOrderListType',
    'BybitTriggerBy',
    'BybitOCOOrderRequest',
    'BybitOCOOrderResponse',
    'BybitBracketOrderRequest',
    'BybitOrderHistoryRequest',
    'BybitOrderBookUpdate',
    'router'
]
