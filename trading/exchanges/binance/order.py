"""
NEXUS AI TRADING SYSTEM - Binance Order Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/order.py
Description: Binance order management with full API integration
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

# Binance imports
from trading.exchanges.binance.base import BinanceBase, BinanceEnvironment
from trading.exchanges.binance.account import (
    BinanceOrderRequest,
    BinanceOrderResponse,
    BinanceOrderSide,
    BinanceOrderType,
    BinanceOrderStatus,
    BinanceTimeInForce
)
from trading.exchanges.binance.exceptions import (
    BinanceException,
    BinanceOrderError,
    BinanceErrorCode,
    BinanceErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BinanceOrderListStatus(str, Enum):
    """Binance order list status"""
    EXECUTING = "EXECUTING"
    ALL_DONE = "ALL_DONE"
    REJECTED = "REJECTED"


class BinanceOrderListType(str, Enum):
    """Binance order list types"""
    OCO = "OCO"  # One Cancels Other
    BRACKET = "BRACKET"  # Bracket order


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BinanceOCOOrderRequest(BaseModel):
    """Binance OCO order request"""
    symbol: str
    side: BinanceOrderSide
    quantity: float
    price: float  # Limit price
    stop_price: float  # Stop price
    stop_limit_price: Optional[float] = None
    stop_time_in_force: BinanceTimeInForce = BinanceTimeInForce.GTC
    limit_time_in_force: BinanceTimeInForce = BinanceTimeInForce.GTC
    client_order_id: Optional[str] = None
    recv_window: int = 5000


class BinanceOCOOrderResponse(BaseModel):
    """Binance OCO order response"""
    order_list_id: int
    contingency_type: str
    list_status_type: str
    list_order_status: BinanceOrderListStatus
    order_ids: List[int]
    orders: List[BinanceOrderResponse]
    client_order_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BinanceOrderHistoryRequest(BaseModel):
    """Binance order history request"""
    symbol: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 500
    order_id: Optional[int] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BinanceOrderBookUpdate:
    """Binance order book update"""
    symbol: str
    order_id: int
    client_order_id: str
    price: float
    quantity: float
    executed_quantity: float
    status: str
    timestamp: datetime


# =============================================================================
# BINANCE ORDER
# =============================================================================

class BinanceOrder(BinanceBase):
    """
    Binance Order Management with full API integration.
    
    Features:
    - Place orders (limit, market, stop, stop-limit, OCO, bracket)
    - Cancel orders
    - Get order status
    - Order history
    - Open orders
    - Order lists
    - Order book updates
    - WebSocket order updates
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: BinanceEnvironment = BinanceEnvironment.TESTNET,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BinanceOrder.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            environment: Binance environment
            config: Exchange configuration
        """
        super().__init__(api_key, api_secret, environment, config)
        
        # Error handler
        self._error_handler = BinanceErrorHandler()
        
        # Order cache
        self._order_cache: Dict[int, BinanceOrderResponse] = {}
        self._oco_order_cache: Dict[int, BinanceOCOOrderResponse] = {}
        
        # Order history
        self._order_history: List[BinanceOrderResponse] = []
        
        # WebSocket order streams
        self._order_streams: Dict[str, Any] = {}
        
        logger.info("BinanceOrder initialized")

    # =========================================================================
    # Place Orders
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: BinanceOrderRequest
    ) -> BinanceOrderResponse:
        """
        Place an order on Binance.
        
        Args:
            request: Order request
            
        Returns:
            BinanceOrderResponse: Order response
        """
        try:
            # Prepare order parameters
            params = {
                'symbol': request.symbol,
                'side': request.side.value,
                'type': request.order_type.value,
                'quantity': request.quantity,
                'timestamp': int(time.time() * 1000),
                'recvWindow': request.recv_window
            }
            
            if request.price:
                params['price'] = request.price
            
            if request.stop_price:
                params['stopPrice'] = request.stop_price
            
            if request.time_in_force:
                params['timeInForce'] = request.time_in_force.value
            
            if request.reduce_only:
                params['reduceOnly'] = 'true'
            
            if request.post_only:
                params['postOnly'] = 'true'
            
            if request.client_order_id:
                params['newClientOrderId'] = request.client_order_id
            
            if request.new_order_resp_type:
                params['newOrderRespType'] = request.new_order_resp_type
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/api/v3/order',
                params=params,
                signed=True,
                weight=1
            )
            
            # Parse response
            order_response = BinanceOrderResponse(
                order_id=response.get('orderId'),
                client_order_id=response.get('clientOrderId'),
                symbol=response.get('symbol'),
                side=BinanceOrderSide(response.get('side')),
                order_type=BinanceOrderType(response.get('type')),
                status=BinanceOrderStatus(response.get('status')),
                price=float(response.get('price', 0)),
                avg_price=float(response.get('avgPrice', 0)),
                quantity=float(response.get('origQty', 0)),
                executed_quantity=float(response.get('executedQty', 0)),
                cummulative_quote_qty=float(response.get('cummulativeQuoteQty', 0)),
                time_in_force=BinanceTimeInForce(response.get('timeInForce', 'GTC')),
                stop_price=float(response.get('stopPrice')) if response.get('stopPrice') else None,
                reduce_only=response.get('reduceOnly', False),
                post_only=response.get('postOnly', False),
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
        request: BinanceOCOOrderRequest
    ) -> BinanceOCOOrderResponse:
        """
        Place an OCO (One Cancels Other) order.
        
        Args:
            request: OCO order request
            
        Returns:
            BinanceOCOOrderResponse: OCO order response
        """
        try:
            # Prepare OCO parameters
            params = {
                'symbol': request.symbol,
                'side': request.side.value,
                'quantity': request.quantity,
                'price': request.price,
                'stopPrice': request.stop_price,
                'timestamp': int(time.time() * 1000),
                'recvWindow': request.recv_window
            }
            
            if request.stop_limit_price:
                params['stopLimitPrice'] = request.stop_limit_price
            
            if request.stop_time_in_force:
                params['stopTimeInForce'] = request.stop_time_in_force.value
            
            if request.limit_time_in_force:
                params['limitTimeInForce'] = request.limit_time_in_force.value
            
            if request.client_order_id:
                params['newClientOrderId'] = request.client_order_id
            
            # Place OCO order
            response = await self._request(
                method='POST',
                endpoint='/api/v3/orderList/oco',
                params=params,
                signed=True,
                weight=1
            )
            
            # Parse response
            oco_response = BinanceOCOOrderResponse(
                order_list_id=response.get('orderListId'),
                contingency_type=response.get('contingencyType', 'OCO'),
                list_status_type=response.get('listStatusType', 'EXECUTING'),
                list_order_status=BinanceOrderListStatus(response.get('listOrderStatus', 'EXECUTING')),
                order_ids=response.get('orderIds', []),
                orders=[],  # Would parse orders if needed
                client_order_id=response.get('clientOrderId'),
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

    # =========================================================================
    # Cancel Orders
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_order(
        self,
        order_id: int,
        symbol: str
    ) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            symbol: Symbol
            
        Returns:
            bool: Success indicator
        """
        try:
            params = {
                'symbol': symbol,
                'orderId': order_id,
                'timestamp': int(time.time() * 1000)
            }
            
            response = await self._request(
                method='DELETE',
                endpoint='/api/v3/order',
                params=params,
                signed=True,
                weight=1
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
            params = {
                'symbol': symbol,
                'timestamp': int(time.time() * 1000)
            }
            
            response = await self._request(
                method='DELETE',
                endpoint='/api/v3/openOrders',
                params=params,
                signed=True,
                weight=1
            )
            
            cancelled_count = len(response) if isinstance(response, list) else 0
            
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
    async def get_order(
        self,
        order_id: int,
        symbol: str
    ) -> Optional[BinanceOrderResponse]:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            symbol: Symbol
            
        Returns:
            Optional[BinanceOrderResponse]: Order details
        """
        try:
            # Check cache
            if order_id in self._order_cache:
                return self._order_cache[order_id]
            
            params = {
                'symbol': symbol,
                'orderId': order_id,
                'timestamp': int(time.time() * 1000)
            }
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/order',
                params=params,
                signed=True,
                weight=1
            )
            
            order_response = BinanceOrderResponse(
                order_id=response.get('orderId'),
                client_order_id=response.get('clientOrderId'),
                symbol=response.get('symbol'),
                side=BinanceOrderSide(response.get('side')),
                order_type=BinanceOrderType(response.get('type')),
                status=BinanceOrderStatus(response.get('status')),
                price=float(response.get('price', 0)),
                avg_price=float(response.get('avgPrice', 0)),
                quantity=float(response.get('origQty', 0)),
                executed_quantity=float(response.get('executedQty', 0)),
                cummulative_quote_qty=float(response.get('cummulativeQuoteQty', 0)),
                time_in_force=BinanceTimeInForce(response.get('timeInForce', 'GTC')),
                stop_price=float(response.get('stopPrice')) if response.get('stopPrice') else None,
                reduce_only=response.get('reduceOnly', False),
                post_only=response.get('postOnly', False),
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
    async def get_open_orders(self, symbol: str) -> List[BinanceOrderResponse]:
        """
        Get open orders for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            List[BinanceOrderResponse]: Open orders
        """
        try:
            params = {
                'symbol': symbol,
                'timestamp': int(time.time() * 1000)
            }
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/openOrders',
                params=params,
                signed=True,
                weight=1
            )
            
            orders = []
            for data in response:
                order_response = BinanceOrderResponse(
                    order_id=data.get('orderId'),
                    client_order_id=data.get('clientOrderId'),
                    symbol=data.get('symbol'),
                    side=BinanceOrderSide(data.get('side')),
                    order_type=BinanceOrderType(data.get('type')),
                    status=BinanceOrderStatus(data.get('status')),
                    price=float(data.get('price', 0)),
                    avg_price=float(data.get('avgPrice', 0)),
                    quantity=float(data.get('origQty', 0)),
                    executed_quantity=float(data.get('executedQty', 0)),
                    cummulative_quote_qty=float(data.get('cummulativeQuoteQty', 0)),
                    time_in_force=BinanceTimeInForce(data.get('timeInForce', 'GTC')),
                    stop_price=float(data.get('stopPrice')) if data.get('stopPrice') else None,
                    reduce_only=data.get('reduceOnly', False),
                    post_only=data.get('postOnly', False),
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
        request: BinanceOrderHistoryRequest
    ) -> List[BinanceOrderResponse]:
        """
        Get order history.
        
        Args:
            request: Order history request
            
        Returns:
            List[BinanceOrderResponse]: Order history
        """
        try:
            params = {
                'symbol': request.symbol,
                'limit': request.limit,
                'timestamp': int(time.time() * 1000)
            }
            
            if request.start_time:
                params['startTime'] = int(request.start_time.timestamp() * 1000)
            
            if request.end_time:
                params['endTime'] = int(request.end_time.timestamp() * 1000)
            
            if request.order_id:
                params['orderId'] = request.order_id
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/allOrders',
                params=params,
                signed=True,
                weight=1
            )
            
            orders = []
            for data in response:
                order_response = BinanceOrderResponse(
                    order_id=data.get('orderId'),
                    client_order_id=data.get('clientOrderId'),
                    symbol=data.get('symbol'),
                    side=BinanceOrderSide(data.get('side')),
                    order_type=BinanceOrderType(data.get('type')),
                    status=BinanceOrderStatus(data.get('status')),
                    price=float(data.get('price', 0)),
                    avg_price=float(data.get('avgPrice', 0)),
                    quantity=float(data.get('origQty', 0)),
                    executed_quantity=float(data.get('executedQty', 0)),
                    cummulative_quote_qty=float(data.get('cummulativeQuoteQty', 0)),
                    time_in_force=BinanceTimeInForce(data.get('timeInForce', 'GTC')),
                    stop_price=float(data.get('stopPrice')) if data.get('stopPrice') else None,
                    reduce_only=data.get('reduceOnly', False),
                    post_only=data.get('postOnly', False),
                    created_at=datetime.fromtimestamp(data.get('time', 0) / 1000),
                    updated_at=datetime.fromtimestamp(data.get('updateTime', 0) / 1000)
                )
                orders.append(order_response)
            
            # Update history
            self._order_history.extend(orders)
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting order history: {e}")
            return []

    # =========================================================================
    # Order Lists
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order_list(
        self,
        order_list_id: int
    ) -> Optional[BinanceOCOOrderResponse]:
        """
        Get order list details.
        
        Args:
            order_list_id: Order list ID
            
        Returns:
            Optional[BinanceOCOOrderResponse]: Order list details
        """
        try:
            # Check cache
            if order_list_id in self._oco_order_cache:
                return self._oco_order_cache[order_list_id]
            
            params = {
                'orderListId': order_list_id,
                'timestamp': int(time.time() * 1000)
            }
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/orderList',
                params=params,
                signed=True,
                weight=1
            )
            
            oco_response = BinanceOCOOrderResponse(
                order_list_id=response.get('orderListId'),
                contingency_type=response.get('contingencyType', 'OCO'),
                list_status_type=response.get('listStatusType', 'EXECUTING'),
                list_order_status=BinanceOrderListStatus(response.get('listOrderStatus', 'EXECUTING')),
                order_ids=response.get('orderIds', []),
                orders=[],
                client_order_id=response.get('clientOrderId'),
                created_at=datetime.fromtimestamp(response.get('transactionTime', 0) / 1000),
                updated_at=datetime.utcnow()
            )
            
            # Cache
            self._oco_order_cache[order_list_id] = oco_response
            
            return oco_response
            
        except Exception as e:
            logger.error(f"Error getting order list {order_list_id}: {e}")
            return None

    # =========================================================================
    # WebSocket Order Streams
    # =========================================================================

    async def subscribe_order_stream(
        self,
        symbol: str,
        callback: callable
    ) -> None:
        """
        Subscribe to order stream for a symbol.
        
        Args:
            symbol: Symbol
            callback: Callback function
        """
        try:
            stream_key = f"{symbol.lower()}@order"
            
            # Connect to WebSocket
            ws_url = f"{self.ws_url}/{stream_key}"
            ws = await websockets.connect(ws_url)
            
            self._order_streams[stream_key] = ws
            
            # Start receiving messages
            asyncio.create_task(self._receive_order_stream(stream_key, callback))
            
            logger.info(f"Subscribed to order stream for {symbol}")
            
        except Exception as e:
            logger.error(f"Error subscribing to order stream: {e}")
            raise

    async def _receive_order_stream(
        self,
        stream_key: str,
        callback: callable
    ) -> None:
        """Receive order stream messages"""
        ws = self._order_streams.get(stream_key)
        if not ws:
            return
        
        try:
            async for message in ws:
                data = json.loads(message)
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in order stream callback: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"Order stream closed: {stream_key}")
        except Exception as e:
            logger.error(f"Error receiving order stream: {e}")

    async def unsubscribe_order_stream(self, symbol: str) -> None:
        """
        Unsubscribe from order stream.
        
        Args:
            symbol: Symbol
        """
        stream_key = f"{symbol.lower()}@order"
        if stream_key in self._order_streams:
            ws = self._order_streams[stream_key]
            await ws.close()
            del self._order_streams[stream_key]
            logger.info(f"Unsubscribed from order stream for {symbol}")

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _parse_order_response(self, data: Dict[str, Any]) -> BinanceOrderResponse:
        """Parse order response"""
        return BinanceOrderResponse(
            order_id=data.get('orderId'),
            client_order_id=data.get('clientOrderId'),
            symbol=data.get('symbol'),
            side=BinanceOrderSide(data.get('side')),
            order_type=BinanceOrderType(data.get('type')),
            status=BinanceOrderStatus(data.get('status')),
            price=float(data.get('price', 0)),
            avg_price=float(data.get('avgPrice', 0)),
            quantity=float(data.get('origQty', 0)),
            executed_quantity=float(data.get('executedQty', 0)),
            cummulative_quote_qty=float(data.get('cummulativeQuoteQty', 0)),
            time_in_force=BinanceTimeInForce(data.get('timeInForce', 'GTC')),
            stop_price=float(data.get('stopPrice')) if data.get('stopPrice') else None,
            reduce_only=data.get('reduceOnly', False),
            post_only=data.get('postOnly', False),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Binance order module"""
        # Close WebSocket streams
        for stream_key in list(self._order_streams.keys()):
            await self.unsubscribe_order_stream(stream_key)
        
        await super().close()
        
        self._order_cache.clear()
        self._oco_order_cache.clear()
        self._order_history.clear()
        
        logger.info("BinanceOrder closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/binance/order", tags=["Binance Order"])


async def get_order(
    api_key: str = Query(..., description="Binance API Key"),
    api_secret: str = Query(..., description="Binance API Secret"),
    environment: BinanceEnvironment = Query(BinanceEnvironment.TESTNET)
) -> BinanceOrder:
    """Dependency to get BinanceOrder instance"""
    return BinanceOrder(api_key, api_secret, environment)


@router.post("/place")
async def place_order(
    request: BinanceOrderRequest,
    order: BinanceOrder = Depends(get_order)
):
    """Place an order"""
    return await order.place_order(request)


@router.post("/place/oco")
async def place_oco_order(
    request: BinanceOCOOrderRequest,
    order: BinanceOrder = Depends(get_order)
):
    """Place an OCO order"""
    return await order.place_oco_order(request)


@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    symbol: str = Query(..., description="Symbol"),
    order: BinanceOrder = Depends(get_order)
):
    """Cancel an order"""
    success = await order.cancel_order(order_id, symbol)
    return {"success": success}


@router.delete("/open/{symbol}")
async def cancel_open_orders(
    symbol: str,
    order: BinanceOrder = Depends(get_order)
):
    """Cancel all open orders for a symbol"""
    count = await order.cancel_open_orders(symbol)
    return {"cancelled": count}


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    symbol: str = Query(..., description="Symbol"),
    order: BinanceOrder = Depends(get_order)
):
    """Get order details"""
    return await order.get_order(order_id, symbol)


@router.get("/open/{symbol}")
async def get_open_orders(
    symbol: str,
    order: BinanceOrder = Depends(get_order)
):
    """Get open orders for a symbol"""
    return await order.get_open_orders(symbol)


@router.post("/history")
async def get_order_history(
    request: BinanceOrderHistoryRequest,
    order: BinanceOrder = Depends(get_order)
):
    """Get order history"""
    return await order.get_order_history(request)


@router.get("/list/{order_list_id}")
async def get_order_list(
    order_list_id: int,
    order: BinanceOrder = Depends(get_order)
):
    """Get order list details"""
    return await order.get_order_list(order_list_id)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BinanceOrder',
    'BinanceOrderListStatus',
    'BinanceOrderListType',
    'BinanceOCOOrderRequest',
    'BinanceOCOOrderResponse',
    'BinanceOrderHistoryRequest',
    'BinanceOrderBookUpdate',
    'router'
]
