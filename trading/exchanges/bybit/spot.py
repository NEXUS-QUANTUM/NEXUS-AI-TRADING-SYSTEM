"""
NEXUS AI TRADING SYSTEM - Bybit Spot Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/spot.py
Description: Bybit spot trading with full API integration
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
    BybitTimeInForce
)
from trading.exchanges.bybit.market import BybitMarket, BybitMarketType
from trading.exchanges.bybit.order import (
    BybitOrder,
    BybitOCOOrderRequest,
    BybitOCOOrderResponse,
    BybitBracketOrderRequest
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

class BybitSpotOrderType(str, Enum):
    """Bybit spot order types"""
    LIMIT = "Limit"
    MARKET = "Market"
    STOP = "Stop"
    STOP_LIMIT = "StopLimit"
    TAKE_PROFIT = "TakeProfit"
    TAKE_PROFIT_LIMIT = "TakeProfitLimit"


class BybitSpotOrderSide(str, Enum):
    """Bybit spot order sides"""
    BUY = "Buy"
    SELL = "Sell"


class BybitSpotTimeInForce(str, Enum):
    """Bybit spot time in force"""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "PostOnly"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BybitSpotOrderRequest(BaseModel):
    """Bybit spot order request"""
    symbol: str
    side: BybitSpotOrderSide
    order_type: BybitSpotOrderType = BybitSpotOrderType.LIMIT
    qty: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: BybitSpotTimeInForce = BybitSpotTimeInForce.GTC
    reduce_only: bool = False
    close_on_trigger: bool = False
    order_link_id: Optional[str] = None


class BybitSpotOrderResponse(BaseModel):
    """Bybit spot order response"""
    order_id: str
    order_link_id: str
    symbol: str
    side: BybitSpotOrderSide
    order_type: BybitSpotOrderType
    status: BybitOrderStatus
    price: float
    avg_price: float
    qty: float
    cum_exec_qty: float
    cum_exec_value: float
    time_in_force: BybitSpotTimeInForce
    stop_price: Optional[float] = None
    reduce_only: bool
    close_on_trigger: bool
    created_at: datetime
    updated_at: datetime


class BybitSpotAccountInfo(BaseModel):
    """Bybit spot account information"""
    account_id: str
    total_equity: float
    available_balance: float
    used_margin: float
    margin_ratio: float
    balances: Dict[str, BybitBalance]
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BybitSpotStreamConfig:
    """Bybit spot stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BYBIT SPOT
# =============================================================================

class BybitSpot(BybitBase):
    """
    Bybit Spot Trading with full API integration.
    
    Features:
    - Spot trading
    - Balance management
    - Order management
    - Market data
    - Account management
    - WebSocket streams
    - OCO orders
    - Bracket orders
    - Order history
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: BybitEnvironment = BybitEnvironment.TESTNET,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BybitSpot.
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            environment: Bybit environment
            config: Exchange configuration
        """
        super().__init__(api_key, api_secret, environment, BybitCategory.SPOT, config)
        
        # Initialize components
        self.market = BybitMarket(config, environment)
        self.order = BybitOrder(api_key, api_secret, environment, BybitCategory.SPOT, config)
        
        # Error handler
        self._error_handler = BybitErrorHandler()
        
        # Cache
        self._account_cache: Optional[BybitSpotAccountInfo] = None
        self._balance_cache: Dict[str, BybitBalance] = {}
        
        logger.info("BybitSpot initialized")

    # =========================================================================
    # Session Management
    # =========================================================================

    async def __aenter__(self):
        """Async context manager entry"""
        await self.market.__aenter__()
        await self.order.__aenter__()
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.market.__aexit__(exc_type, exc_val, exc_tb)
        await self.order.__aexit__(exc_type, exc_val, exc_tb)
        await super().__aexit__(exc_type, exc_val, exc_tb)

    # =========================================================================
    # Account Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_account_info(self) -> BybitSpotAccountInfo:
        """
        Get spot account information.
        
        Returns:
            BybitSpotAccountInfo: Account information
        """
        try:
            # Check cache
            if self._account_cache and (datetime.utcnow() - self._account_cache.timestamp).seconds < 60:
                return self._account_cache
            
            response = await self._request(
                method='GET',
                endpoint='/v5/account/info',
                signed=True
            )
            
            data = response
            
            balances = {}
            total_equity = 0
            available_balance = 0
            
            for balance_data in data.get('balances', []):
                coin = balance_data['coin']
                free = float(balance_data.get('free', 0))
                locked = float(balance_data.get('locked', 0))
                total = free + locked
                
                if total > 0:
                    balance = BybitBalance(
                        coin=coin,
                        equity=total,
                        available=free,
                        used_margin=0,
                        order_margin=0,
                        position_margin=0,
                        total=total
                    )
                    balances[coin] = balance
                    
                    # Get price for USD value
                    price = await self._get_price(coin)
                    if price:
                        total_equity += total * price
                        available_balance += free * price
            
            account_info = BybitSpotAccountInfo(
                account_id=data.get('accountId', ''),
                total_equity=total_equity,
                available_balance=available_balance,
                used_margin=0,
                margin_ratio=0,
                balances=balances,
                positions=[],
                orders=[],
                timestamp=datetime.utcnow()
            )
            
            self._account_cache = account_info
            self._balance_cache = balances
            
            return account_info
            
        except Exception as e:
            logger.error(f"Error getting spot account info: {e}")
            raise

    async def _get_price(self, coin: str) -> Optional[float]:
        """Get price of coin in USD"""
        try:
            if coin == 'USDT':
                return 1.0
            
            symbol = f"{coin}USDT"
            ticker = await self.market.get_ticker(symbol, BybitMarketType.SPOT)
            return ticker.price
            
        except Exception as e:
            logger.warning(f"Error getting price for {coin}: {e}")
            return None

    # =========================================================================
    # Balance Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_balance(self, coin: str) -> Optional[BybitBalance]:
        """
        Get balance for a coin.
        
        Args:
            coin: Coin symbol
            
        Returns:
            Optional[BybitBalance]: Balance
        """
        try:
            # Check cache
            if coin in self._balance_cache:
                cached = self._balance_cache[coin]
                if self._account_cache and (datetime.utcnow() - self._account_cache.timestamp).seconds < 60:
                    return cached
            
            account = await self.get_account_info()
            return account.balances.get(coin)
            
        except Exception as e:
            logger.error(f"Error getting balance for {coin}: {e}")
            return None

    @retry_async(max_attempts=3, delay=0.5)
    async def get_all_balances(self) -> Dict[str, BybitBalance]:
        """
        Get all balances.
        
        Returns:
            Dict[str, BybitBalance]: All balances
        """
        try:
            account = await self.get_account_info()
            return account.balances
            
        except Exception as e:
            logger.error(f"Error getting all balances: {e}")
            return {}

    # =========================================================================
    # Order Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: BybitSpotOrderRequest
    ) -> BybitSpotOrderResponse:
        """
        Place a spot order.
        
        Args:
            request: Order request
            
        Returns:
            BybitSpotOrderResponse: Order response
        """
        try:
            # Convert to BybitOrderRequest
            order_request = BybitOrderRequest(
                symbol=request.symbol,
                side=BybitOrderSide(request.side.value),
                order_type=BybitOrderType(request.order_type.value),
                qty=request.qty,
                price=request.price,
                stop_price=request.stop_price,
                time_in_force=BybitTimeInForce(request.time_in_force.value),
                reduce_only=request.reduce_only,
                close_on_trigger=request.close_on_trigger,
                order_link_id=request.order_link_id
            )
            
            # Place order
            order_response = await self.order.place_order(order_request)
            
            # Convert to spot order response
            spot_response = BybitSpotOrderResponse(
                order_id=order_response.order_id,
                order_link_id=order_response.order_link_id,
                symbol=order_response.symbol,
                side=BybitSpotOrderSide(order_response.side.value),
                order_type=BybitSpotOrderType(order_response.order_type.value),
                status=order_response.status,
                price=order_response.price,
                avg_price=order_response.avg_price,
                qty=order_response.qty,
                cum_exec_qty=order_response.cum_exec_qty,
                cum_exec_value=order_response.cum_exec_value,
                time_in_force=BybitSpotTimeInForce(order_response.time_in_force.value),
                stop_price=order_response.stop_price,
                reduce_only=order_response.reduce_only,
                close_on_trigger=order_response.close_on_trigger,
                created_at=order_response.created_at,
                updated_at=order_response.updated_at
            )
            
            logger.info(f"Spot order placed: {spot_response.order_id} for {request.symbol}")
            return spot_response
            
        except Exception as e:
            logger.error(f"Error placing spot order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def place_oco_order(
        self,
        request: BybitOCOOrderRequest
    ) -> BybitOCOOrderResponse:
        """
        Place an OCO order.
        
        Args:
            request: OCO order request
            
        Returns:
            BybitOCOOrderResponse: OCO order response
        """
        try:
            return await self.order.place_oco_order(request)
            
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
            return await self.order.place_bracket_order(request)
            
        except Exception as e:
            logger.error(f"Error placing bracket order: {e}")
            raise

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
            return await self.order.cancel_order(order_id, symbol)
            
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
            return await self.order.cancel_open_orders(symbol)
            
        except Exception as e:
            logger.error(f"Error cancelling open orders for {symbol}: {e}")
            return 0

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order(self, order_id: str, symbol: str) -> Optional[BybitSpotOrderResponse]:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            symbol: Symbol
            
        Returns:
            Optional[BybitSpotOrderResponse]: Order details
        """
        try:
            order_response = await self.order.get_order(order_id, symbol)
            if not order_response:
                return None
            
            return BybitSpotOrderResponse(
                order_id=order_response.order_id,
                order_link_id=order_response.order_link_id,
                symbol=order_response.symbol,
                side=BybitSpotOrderSide(order_response.side.value),
                order_type=BybitSpotOrderType(order_response.order_type.value),
                status=order_response.status,
                price=order_response.price,
                avg_price=order_response.avg_price,
                qty=order_response.qty,
                cum_exec_qty=order_response.cum_exec_qty,
                cum_exec_value=order_response.cum_exec_value,
                time_in_force=BybitSpotTimeInForce(order_response.time_in_force.value),
                stop_price=order_response.stop_price,
                reduce_only=order_response.reduce_only,
                close_on_trigger=order_response.close_on_trigger,
                created_at=order_response.created_at,
                updated_at=order_response.updated_at
            )
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    @retry_async(max_attempts=3, delay=0.5)
    async def get_open_orders(self, symbol: str) -> List[BybitSpotOrderResponse]:
        """
        Get open orders for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            List[BybitSpotOrderResponse]: Open orders
        """
        try:
            orders = await self.order.get_open_orders(symbol)
            
            spot_orders = []
            for order in orders:
                spot_orders.append(BybitSpotOrderResponse(
                    order_id=order.order_id,
                    order_link_id=order.order_link_id,
                    symbol=order.symbol,
                    side=BybitSpotOrderSide(order.side.value),
                    order_type=BybitSpotOrderType(order.order_type.value),
                    status=order.status,
                    price=order.price,
                    avg_price=order.avg_price,
                    qty=order.qty,
                    cum_exec_qty=order.cum_exec_qty,
                    cum_exec_value=order.cum_exec_value,
                    time_in_force=BybitSpotTimeInForce(order.time_in_force.value),
                    stop_price=order.stop_price,
                    reduce_only=order.reduce_only,
                    close_on_trigger=order.close_on_trigger,
                    created_at=order.created_at,
                    updated_at=order.updated_at
                ))
            
            return spot_orders
            
        except Exception as e:
            logger.error(f"Error getting open orders for {symbol}: {e}")
            return []

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_ticker(self, symbol: str) -> BybitTicker:
        """Get ticker for symbol"""
        return await self.market.get_ticker(symbol, BybitMarketType.SPOT)

    async def get_candles(
        self,
        symbol: str,
        interval: BybitInterval = BybitInterval.ONE_HOUR,
        limit: int = 500
    ) -> List[BybitCandle]:
        """Get candle data"""
        return await self.market.get_candles(symbol, interval, limit, BybitMarketType.SPOT)

    async def get_order_book(
        self,
        symbol: str,
        limit: BybitDepthLevel = BybitDepthLevel.LEVEL_10
    ) -> BybitOrderBook:
        """Get order book"""
        return await self.market.get_order_book(symbol, BybitMarketType.SPOT, limit)

    async def get_recent_trades(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[BybitTrade]:
        """Get recent trades"""
        return await self.market.get_recent_trades(symbol, limit, BybitMarketType.SPOT)

    # =========================================================================
    # WebSocket Streaming
    # =========================================================================

    async def subscribe(
        self,
        config: BybitSpotStreamConfig,
        websocket: WebSocket
    ) -> None:
        """
        Subscribe to spot market streams.
        
        Args:
            config: Stream configuration
            websocket: WebSocket connection
        """
        stream_config = BybitMarketStreamConfig(
            symbol=config.symbol,
            channels=config.channels,
            interval=config.interval,
            depth_level=config.depth_level
        )
        await self.market.subscribe(stream_config, websocket)

    async def unsubscribe(self, stream_key: str) -> None:
        """Unsubscribe from stream"""
        await self.market.unsubscribe(stream_key)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Bybit spot module"""
        await self.market.close()
        await self.order.close()
        await super().close()
        
        self._account_cache = None
        self._balance_cache.clear()
        
        logger.info("BybitSpot closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/bybit/spot", tags=["Bybit Spot"])


async def get_spot(
    api_key: str = Query(..., description="Bybit API Key"),
    api_secret: str = Query(..., description="Bybit API Secret"),
    environment: BybitEnvironment = Query(BybitEnvironment.TESTNET)
) -> BybitSpot:
    """Dependency to get BybitSpot instance"""
    return BybitSpot(api_key, api_secret, environment)


@router.get("/account")
async def get_account_info(
    spot: BybitSpot = Depends(get_spot)
):
    """Get spot account information"""
    return await spot.get_account_info()


@router.get("/balance/{coin}")
async def get_balance(
    coin: str,
    spot: BybitSpot = Depends(get_spot)
):
    """Get balance for a coin"""
    return await spot.get_balance(coin)


@router.get("/balances")
async def get_all_balances(
    spot: BybitSpot = Depends(get_spot)
):
    """Get all balances"""
    return await spot.get_all_balances()


@router.post("/order")
async def place_order(
    request: BybitSpotOrderRequest,
    spot: BybitSpot = Depends(get_spot)
):
    """Place a spot order"""
    return await spot.place_order(request)


@router.post("/order/oco")
async def place_oco_order(
    request: BybitOCOOrderRequest,
    spot: BybitSpot = Depends(get_spot)
):
    """Place an OCO order"""
    return await spot.place_oco_order(request)


@router.post("/order/bracket")
async def place_bracket_order(
    request: BybitBracketOrderRequest,
    spot: BybitSpot = Depends(get_spot)
):
    """Place a bracket order"""
    return await spot.place_bracket_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    symbol: str = Query(..., description="Symbol"),
    spot: BybitSpot = Depends(get_spot)
):
    """Cancel an order"""
    success = await spot.cancel_order(order_id, symbol)
    return {"success": success}


@router.delete("/orders/{symbol}")
async def cancel_open_orders(
    symbol: str,
    spot: BybitSpot = Depends(get_spot)
):
    """Cancel all open orders for a symbol"""
    count = await spot.cancel_open_orders(symbol)
    return {"cancelled": count}


@router.get("/order/{order_id}")
async def get_order(
    order_id: str,
    symbol: str = Query(..., description="Symbol"),
    spot: BybitSpot = Depends(get_spot)
):
    """Get order details"""
    return await spot.get_order(order_id, symbol)


@router.get("/orders/open/{symbol}")
async def get_open_orders(
    symbol: str,
    spot: BybitSpot = Depends(get_spot)
):
    """Get open orders for a symbol"""
    return await spot.get_open_orders(symbol)


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    spot: BybitSpot = Depends(get_spot)
):
    """Get ticker for symbol"""
    return await spot.get_ticker(symbol)


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    interval: BybitInterval = Query(BybitInterval.ONE_HOUR),
    limit: int = Query(500, le=1000),
    spot: BybitSpot = Depends(get_spot)
):
    """Get candle data"""
    return await spot.get_candles(symbol, interval, limit)


@router.get("/order-book/{symbol}")
async def get_order_book(
    symbol: str,
    limit: BybitDepthLevel = Query(BybitDepthLevel.LEVEL_10),
    spot: BybitSpot = Depends(get_spot)
):
    """Get order book"""
    return await spot.get_order_book(symbol, limit)


@router.get("/trades/{symbol}")
async def get_recent_trades(
    symbol: str,
    limit: int = Query(100, le=1000),
    spot: BybitSpot = Depends(get_spot)
):
    """Get recent trades"""
    return await spot.get_recent_trades(symbol, limit)


@router.websocket("/ws/{symbol}")
async def spot_websocket(
    websocket: WebSocket,
    symbol: str,
    channels: List[str] = Query(...),
    interval: str = Query(None),
    depth: str = Query(None),
    spot: BybitSpot = Depends(get_spot)
):
    """WebSocket endpoint for spot market data"""
    await websocket.accept()
    
    config = BybitSpotStreamConfig(
        symbol=symbol,
        channels=channels,
        interval=interval,
        depth_level=depth
    )
    
    await spot.subscribe(config, websocket)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await spot.unsubscribe(f"{symbol}_{'_'.join(channels)}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitSpot',
    'BybitSpotOrderType',
    'BybitSpotOrderSide',
    'BybitSpotTimeInForce',
    'BybitSpotOrderRequest',
    'BybitSpotOrderResponse',
    'BybitSpotAccountInfo',
    'BybitSpotStreamConfig',
    'router'
]
