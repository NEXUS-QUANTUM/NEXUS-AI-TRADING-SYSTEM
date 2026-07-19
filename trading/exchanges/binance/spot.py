"""
NEXUS AI TRADING SYSTEM - Binance Spot Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/spot.py
Description: Binance spot trading with full API integration
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

# Binance imports
from trading.exchanges.binance.base import BinanceBase, BinanceEnvironment, BinanceInterval
from trading.exchanges.binance.account import (
    BinanceAccount,
    BinanceCredentials,
    BinanceAccountInfo,
    BinanceBalance,
    BinanceOrderRequest,
    BinanceOrderResponse,
    BinanceOrderSide,
    BinanceOrderType,
    BinanceOrderStatus,
    BinanceTimeInForce
)
from trading.exchanges.binance.market import BinanceMarket, BinanceMarketType
from trading.exchanges.binance.order import BinanceOrder, BinanceOCOOrderRequest, BinanceOCOOrderResponse
from trading.exchanges.binance.exceptions import (
    BinanceException,
    BinanceOrderError,
    BinanceAccountError,
    BinanceErrorCode,
    BinanceErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BinanceSpotOrderType(str, Enum):
    """Binance spot order types"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"


class BinanceSpotOrderSide(str, Enum):
    """Binance spot order sides"""
    BUY = "BUY"
    SELL = "SELL"


class BinanceSpotTimeInForce(str, Enum):
    """Binance spot time in force"""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BinanceSpotOrderRequest(BaseModel):
    """Binance spot order request"""
    symbol: str
    side: BinanceSpotOrderSide
    order_type: BinanceSpotOrderType = BinanceSpotOrderType.LIMIT
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: BinanceSpotTimeInForce = BinanceSpotTimeInForce.GTC
    reduce_only: bool = False
    post_only: bool = False
    client_order_id: Optional[str] = None
    recv_window: int = 5000


class BinanceSpotOrderResponse(BaseModel):
    """Binance spot order response"""
    order_id: int
    client_order_id: str
    symbol: str
    side: BinanceSpotOrderSide
    order_type: BinanceSpotOrderType
    status: BinanceOrderStatus
    price: float
    avg_price: float
    quantity: float
    executed_quantity: float
    cummulative_quote_qty: float
    time_in_force: BinanceSpotTimeInForce
    stop_price: Optional[float] = None
    reduce_only: bool
    post_only: bool
    created_at: datetime
    updated_at: datetime


class BinanceSpotAccountInfo(BaseModel):
    """Binance spot account information"""
    account_id: int
    can_trade: bool
    can_withdraw: bool
    can_deposit: bool
    total_balance: float
    available_balance: float
    balances: Dict[str, BinanceBalance]
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BinanceSpotStreamConfig:
    """Binance spot stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BINANCE SPOT
# =============================================================================

class BinanceSpot(BinanceBase):
    """
    Binance Spot Trading with full API integration.
    
    Features:
    - Spot trading
    - Balance management
    - Order management
    - Market data
    - Account management
    - WebSocket streams
    - OCO orders
    - Order history
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: BinanceEnvironment = BinanceEnvironment.TESTNET,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BinanceSpot.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            environment: Binance environment
            config: Exchange configuration
        """
        super().__init__(api_key, api_secret, environment, config)
        
        # Initialize components
        self.market = BinanceMarket(config, environment)
        self.order = BinanceOrder(api_key, api_secret, environment, config)
        
        # Error handler
        self._error_handler = BinanceErrorHandler()
        
        # Cache
        self._account_cache: Optional[BinanceSpotAccountInfo] = None
        self._balance_cache: Dict[str, BinanceBalance] = {}
        
        logger.info("BinanceSpot initialized")

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
    async def get_account_info(self) -> BinanceSpotAccountInfo:
        """
        Get spot account information.
        
        Returns:
            BinanceSpotAccountInfo: Account information
        """
        try:
            # Check cache
            if self._account_cache and (datetime.utcnow() - self._account_cache.timestamp).seconds < 60:
                return self._account_cache
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/account',
                signed=True,
                weight=5
            )
            
            balances = {}
            total_balance = 0
            available_balance = 0
            
            for balance_data in response.get('balances', []):
                asset = balance_data['asset']
                free = float(balance_data['free'])
                locked = float(balance_data['locked'])
                total = free + locked
                
                if total > 0:
                    balance = BinanceBalance(
                        asset=asset,
                        free=free,
                        locked=locked,
                        total=total
                    )
                    balances[asset] = balance
                    
                    # Get price for USD value
                    price = await self._get_price(asset)
                    if price:
                        total_balance += total * price
                        available_balance += free * price
            
            account_info = BinanceSpotAccountInfo(
                account_id=response.get('accountId'),
                can_trade=response.get('canTrade', False),
                can_withdraw=response.get('canWithdraw', False),
                can_deposit=response.get('canDeposit', False),
                total_balance=total_balance,
                available_balance=available_balance,
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

    async def _get_price(self, asset: str) -> Optional[float]:
        """Get price of asset in USD"""
        try:
            if asset == 'USDT':
                return 1.0
            
            symbol = f"{asset}USDT"
            ticker = await self.market.get_ticker(symbol)
            return ticker.price
            
        except Exception as e:
            logger.warning(f"Error getting price for {asset}: {e}")
            return None

    # =========================================================================
    # Balance Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_balance(self, asset: str) -> Optional[BinanceBalance]:
        """
        Get balance for an asset.
        
        Args:
            asset: Asset symbol
            
        Returns:
            Optional[BinanceBalance]: Balance
        """
        try:
            # Check cache
            if asset in self._balance_cache:
                cached = self._balance_cache[asset]
                if (datetime.utcnow() - self._account_cache.timestamp).seconds < 60:
                    return cached
            
            account = await self.get_account_info()
            return account.balances.get(asset)
            
        except Exception as e:
            logger.error(f"Error getting balance for {asset}: {e}")
            return None

    @retry_async(max_attempts=3, delay=0.5)
    async def get_all_balances(self) -> Dict[str, BinanceBalance]:
        """
        Get all balances.
        
        Returns:
            Dict[str, BinanceBalance]: All balances
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
        request: BinanceSpotOrderRequest
    ) -> BinanceSpotOrderResponse:
        """
        Place a spot order.
        
        Args:
            request: Order request
            
        Returns:
            BinanceSpotOrderResponse: Order response
        """
        try:
            # Convert to BinanceOrderRequest
            order_request = BinanceOrderRequest(
                symbol=request.symbol,
                side=BinanceOrderSide(request.side.value),
                order_type=BinanceOrderType(request.order_type.value),
                quantity=request.quantity,
                price=request.price,
                stop_price=request.stop_price,
                time_in_force=BinanceTimeInForce(request.time_in_force.value),
                reduce_only=request.reduce_only,
                post_only=request.post_only,
                client_order_id=request.client_order_id,
                recv_window=request.recv_window
            )
            
            # Place order
            order_response = await self.order.place_order(order_request)
            
            # Convert to spot order response
            spot_response = BinanceSpotOrderResponse(
                order_id=order_response.order_id,
                client_order_id=order_response.client_order_id,
                symbol=order_response.symbol,
                side=BinanceSpotOrderSide(order_response.side.value),
                order_type=BinanceSpotOrderType(order_response.order_type.value),
                status=order_response.status,
                price=order_response.price,
                avg_price=order_response.avg_price,
                quantity=order_response.quantity,
                executed_quantity=order_response.executed_quantity,
                cummulative_quote_qty=order_response.cummulative_quote_qty,
                time_in_force=BinanceSpotTimeInForce(order_response.time_in_force.value),
                stop_price=order_response.stop_price,
                reduce_only=order_response.reduce_only,
                post_only=order_response.post_only,
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
        request: BinanceOCOOrderRequest
    ) -> BinanceOCOOrderResponse:
        """
        Place an OCO order.
        
        Args:
            request: OCO order request
            
        Returns:
            BinanceOCOOrderResponse: OCO order response
        """
        try:
            return await self.order.place_oco_order(request)
            
        except Exception as e:
            logger.error(f"Error placing OCO order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_order(self, order_id: int, symbol: str) -> bool:
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
    async def get_order(self, order_id: int, symbol: str) -> Optional[BinanceSpotOrderResponse]:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            symbol: Symbol
            
        Returns:
            Optional[BinanceSpotOrderResponse]: Order details
        """
        try:
            order_response = await self.order.get_order(order_id, symbol)
            if not order_response:
                return None
            
            return BinanceSpotOrderResponse(
                order_id=order_response.order_id,
                client_order_id=order_response.client_order_id,
                symbol=order_response.symbol,
                side=BinanceSpotOrderSide(order_response.side.value),
                order_type=BinanceSpotOrderType(order_response.order_type.value),
                status=order_response.status,
                price=order_response.price,
                avg_price=order_response.avg_price,
                quantity=order_response.quantity,
                executed_quantity=order_response.executed_quantity,
                cummulative_quote_qty=order_response.cummulative_quote_qty,
                time_in_force=BinanceSpotTimeInForce(order_response.time_in_force.value),
                stop_price=order_response.stop_price,
                reduce_only=order_response.reduce_only,
                post_only=order_response.post_only,
                created_at=order_response.created_at,
                updated_at=order_response.updated_at
            )
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    @retry_async(max_attempts=3, delay=0.5)
    async def get_open_orders(self, symbol: str) -> List[BinanceSpotOrderResponse]:
        """
        Get open orders for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            List[BinanceSpotOrderResponse]: Open orders
        """
        try:
            orders = await self.order.get_open_orders(symbol)
            
            spot_orders = []
            for order in orders:
                spot_orders.append(BinanceSpotOrderResponse(
                    order_id=order.order_id,
                    client_order_id=order.client_order_id,
                    symbol=order.symbol,
                    side=BinanceSpotOrderSide(order.side.value),
                    order_type=BinanceSpotOrderType(order.order_type.value),
                    status=order.status,
                    price=order.price,
                    avg_price=order.avg_price,
                    quantity=order.quantity,
                    executed_quantity=order.executed_quantity,
                    cummulative_quote_qty=order.cummulative_quote_qty,
                    time_in_force=BinanceSpotTimeInForce(order.time_in_force.value),
                    stop_price=order.stop_price,
                    reduce_only=order.reduce_only,
                    post_only=order.post_only,
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

    async def get_ticker(self, symbol: str) -> BinanceTicker:
        """Get ticker for symbol"""
        return await self.market.get_ticker(symbol, BinanceMarketType.SPOT)

    async def get_candles(
        self,
        symbol: str,
        interval: BinanceInterval = BinanceInterval.ONE_HOUR,
        limit: int = 500
    ) -> List[BinanceCandle]:
        """Get candle data"""
        return await self.market.get_candles(symbol, interval, limit, BinanceMarketType.SPOT)

    async def get_order_book(
        self,
        symbol: str,
        limit: BinanceDepthLevel = BinanceDepthLevel.LEVEL_10
    ) -> BinanceOrderBook:
        """Get order book"""
        return await self.market.get_order_book(symbol, BinanceMarketType.SPOT, limit)

    async def get_recent_trades(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[BinanceTrade]:
        """Get recent trades"""
        return await self.market.get_recent_trades(symbol, limit, BinanceMarketType.SPOT)

    # =========================================================================
    # WebSocket Streaming
    # =========================================================================

    async def subscribe(
        self,
        config: BinanceSpotStreamConfig,
        websocket: WebSocket
    ) -> None:
        """
        Subscribe to spot market streams.
        
        Args:
            config: Stream configuration
            websocket: WebSocket connection
        """
        stream_config = BinanceMarketStreamConfig(
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
        """Close the Binance spot module"""
        await self.market.close()
        await self.order.close()
        await super().close()
        
        self._account_cache = None
        self._balance_cache.clear()
        
        logger.info("BinanceSpot closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/binance/spot", tags=["Binance Spot"])


async def get_spot(
    api_key: str = Query(..., description="Binance API Key"),
    api_secret: str = Query(..., description="Binance API Secret"),
    environment: BinanceEnvironment = Query(BinanceEnvironment.TESTNET)
) -> BinanceSpot:
    """Dependency to get BinanceSpot instance"""
    return BinanceSpot(api_key, api_secret, environment)


@router.get("/account")
async def get_account_info(
    spot: BinanceSpot = Depends(get_spot)
):
    """Get spot account information"""
    return await spot.get_account_info()


@router.get("/balance/{asset}")
async def get_balance(
    asset: str,
    spot: BinanceSpot = Depends(get_spot)
):
    """Get balance for an asset"""
    return await spot.get_balance(asset)


@router.get("/balances")
async def get_all_balances(
    spot: BinanceSpot = Depends(get_spot)
):
    """Get all balances"""
    return await spot.get_all_balances()


@router.post("/order")
async def place_order(
    request: BinanceSpotOrderRequest,
    spot: BinanceSpot = Depends(get_spot)
):
    """Place a spot order"""
    return await spot.place_order(request)


@router.post("/order/oco")
async def place_oco_order(
    request: BinanceOCOOrderRequest,
    spot: BinanceSpot = Depends(get_spot)
):
    """Place an OCO order"""
    return await spot.place_oco_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: int,
    symbol: str = Query(..., description="Symbol"),
    spot: BinanceSpot = Depends(get_spot)
):
    """Cancel an order"""
    success = await spot.cancel_order(order_id, symbol)
    return {"success": success}


@router.delete("/orders/{symbol}")
async def cancel_open_orders(
    symbol: str,
    spot: BinanceSpot = Depends(get_spot)
):
    """Cancel all open orders for a symbol"""
    count = await spot.cancel_open_orders(symbol)
    return {"cancelled": count}


@router.get("/order/{order_id}")
async def get_order(
    order_id: int,
    symbol: str = Query(..., description="Symbol"),
    spot: BinanceSpot = Depends(get_spot)
):
    """Get order details"""
    return await spot.get_order(order_id, symbol)


@router.get("/orders/open/{symbol}")
async def get_open_orders(
    symbol: str,
    spot: BinanceSpot = Depends(get_spot)
):
    """Get open orders for a symbol"""
    return await spot.get_open_orders(symbol)


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    spot: BinanceSpot = Depends(get_spot)
):
    """Get ticker for symbol"""
    return await spot.get_ticker(symbol)


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    interval: BinanceInterval = Query(BinanceInterval.ONE_HOUR),
    limit: int = Query(500, le=1000),
    spot: BinanceSpot = Depends(get_spot)
):
    """Get candle data"""
    return await spot.get_candles(symbol, interval, limit)


@router.get("/order-book/{symbol}")
async def get_order_book(
    symbol: str,
    limit: BinanceDepthLevel = Query(BinanceDepthLevel.LEVEL_10),
    spot: BinanceSpot = Depends(get_spot)
):
    """Get order book"""
    return await spot.get_order_book(symbol, limit)


@router.get("/trades/{symbol}")
async def get_recent_trades(
    symbol: str,
    limit: int = Query(100, le=1000),
    spot: BinanceSpot = Depends(get_spot)
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
    spot: BinanceSpot = Depends(get_spot)
):
    """WebSocket endpoint for spot market data"""
    await websocket.accept()
    
    config = BinanceSpotStreamConfig(
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
    'BinanceSpot',
    'BinanceSpotOrderType',
    'BinanceSpotOrderSide',
    'BinanceSpotTimeInForce',
    'BinanceSpotOrderRequest',
    'BinanceSpotOrderResponse',
    'BinanceSpotAccountInfo',
    'BinanceSpotStreamConfig',
    'router'
]
