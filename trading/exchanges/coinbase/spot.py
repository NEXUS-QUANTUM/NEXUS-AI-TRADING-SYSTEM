"""
NEXUS AI TRADING SYSTEM - Coinbase Spot Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/coinbase/spot.py
Description: Coinbase spot trading with full API integration
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
from shared.constants.trading_constants import ORDER_TYPES, POSITION_DIRECTIONS
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

# Coinbase imports
from trading.exchanges.coinbase.base import CoinbaseBase, CoinbaseEnvironment, CoinbaseGranularity
from trading.exchanges.coinbase.account import (
    CoinbaseAccount,
    CoinbaseCredentials,
    CoinbaseAccountInfo,
    CoinbaseBalance,
    CoinbaseOrderRequest,
    CoinbaseOrderResponse,
    CoinbaseOrderSide,
    CoinbaseOrderType,
    CoinbaseOrderStatus,
    CoinbaseTimeInForce
)
from trading.exchanges.coinbase.market import CoinbaseMarket, CoinbaseMarketType
from trading.exchanges.coinbase.order import (
    CoinbaseOrder,
    CoinbaseOCOOrderRequest,
    CoinbaseOCOOrderResponse,
    CoinbaseBracketOrderRequest
)
from trading.exchanges.coinbase.exceptions import (
    CoinbaseException,
    CoinbaseOrderError,
    CoinbaseAccountError,
    CoinbaseErrorCode,
    CoinbaseErrorHandler
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class CoinbaseSpotOrderType(str, Enum):
    """Coinbase spot order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class CoinbaseSpotOrderSide(str, Enum):
    """Coinbase spot order sides"""
    BUY = "buy"
    SELL = "sell"


class CoinbaseSpotTimeInForce(str, Enum):
    """Coinbase spot time in force"""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    GTD = "GTD"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CoinbaseSpotOrderRequest(BaseModel):
    """Coinbase spot order request"""
    product_id: str
    side: CoinbaseSpotOrderSide
    order_type: CoinbaseSpotOrderType = CoinbaseSpotOrderType.LIMIT
    size: Optional[float] = None
    funds: Optional[float] = None
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: CoinbaseSpotTimeInForce = CoinbaseSpotTimeInForce.GTC
    end_time: Optional[datetime] = None
    post_only: bool = False
    client_order_id: Optional[str] = None


class CoinbaseSpotOrderResponse(BaseModel):
    """Coinbase spot order response"""
    order_id: str
    client_order_id: str
    product_id: str
    side: CoinbaseSpotOrderSide
    order_type: CoinbaseSpotOrderType
    status: CoinbaseOrderStatus
    price: float
    filled_size: float
    size: float
    funds: float
    filled_funds: float
    time_in_force: CoinbaseSpotTimeInForce
    stop_price: Optional[float] = None
    post_only: bool
    created_at: datetime
    done_at: Optional[datetime] = None
    done_reason: Optional[str] = None


class CoinbaseSpotAccountInfo(BaseModel):
    """Coinbase spot account information"""
    account_id: str
    total_balance: float
    available_balance: float
    balances: Dict[str, CoinbaseBalance]
    orders: List[Dict[str, Any]]
    timestamp: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CoinbaseSpotStreamConfig:
    """Coinbase spot stream configuration"""
    product_ids: List[str]
    channels: List[str]
    granularity: Optional[str] = None


# =============================================================================
# COINBASE SPOT
# =============================================================================

class CoinbaseSpot(CoinbaseBase):
    """
    Coinbase Spot Trading with full API integration.
    
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
        passphrase: str,
        environment: CoinbaseEnvironment = CoinbaseEnvironment.SANDBOX,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize CoinbaseSpot.
        
        Args:
            api_key: Coinbase API key
            api_secret: Coinbase API secret
            passphrase: Coinbase passphrase
            environment: Coinbase environment
            config: Exchange configuration
        """
        super().__init__(api_key, api_secret, passphrase, environment, config)
        
        # Initialize components
        self.market = CoinbaseMarket(config, environment)
        self.order = CoinbaseOrder(api_key, api_secret, passphrase, environment, config)
        
        # Error handler
        self._error_handler = CoinbaseErrorHandler()
        
        # Cache
        self._account_cache: Optional[CoinbaseSpotAccountInfo] = None
        self._balance_cache: Dict[str, CoinbaseBalance] = {}
        
        logger.info("CoinbaseSpot initialized")

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
    async def get_account_info(self) -> CoinbaseSpotAccountInfo:
        """
        Get spot account information.
        
        Returns:
            CoinbaseSpotAccountInfo: Account information
        """
        try:
            # Check cache
            if self._account_cache and (datetime.utcnow() - self._account_cache.timestamp).seconds < 60:
                return self._account_cache
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/brokerage/accounts',
                signed=True
            )
            
            balances = {}
            total_balance = 0
            available_balance = 0
            
            for account in response.get('accounts', []):
                currency = account.get('currency')
                balance = float(account.get('balance', 0))
                available = float(account.get('available_balance', {}).get('value', 0))
                hold = float(account.get('hold', {}).get('value', 0))
                
                if balance > 0:
                    balance_obj = CoinbaseBalance(
                        currency=currency,
                        amount=balance,
                        available=available,
                        hold=hold
                    )
                    balances[currency] = balance_obj
                    
                    # Get price for USD value
                    price = await self._get_price(currency)
                    if price:
                        total_balance += balance * price
                        available_balance += available * price
            
            account_info = CoinbaseSpotAccountInfo(
                account_id=response.get('id', ''),
                total_balance=total_balance,
                available_balance=available_balance,
                balances=balances,
                orders=[],
                timestamp=datetime.utcnow()
            )
            
            self._account_cache = account_info
            self._balance_cache = balances
            
            return account_info
            
        except Exception as e:
            logger.error(f"Error getting spot account info: {e}")
            raise

    async def _get_price(self, currency: str) -> Optional[float]:
        """Get price of currency in USD"""
        try:
            if currency == 'USD':
                return 1.0
            
            product_id = f"{currency}-USD"
            ticker = await self.market.get_ticker(product_id)
            return ticker.price
            
        except Exception as e:
            logger.warning(f"Error getting price for {currency}: {e}")
            return None

    # =========================================================================
    # Balance Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_balance(self, currency: str) -> Optional[CoinbaseBalance]:
        """
        Get balance for a currency.
        
        Args:
            currency: Currency symbol
            
        Returns:
            Optional[CoinbaseBalance]: Balance
        """
        try:
            # Check cache
            if currency in self._balance_cache:
                return self._balance_cache[currency]
            
            account = await self.get_account_info()
            return account.balances.get(currency)
            
        except Exception as e:
            logger.error(f"Error getting balance for {currency}: {e}")
            return None

    @retry_async(max_attempts=3, delay=0.5)
    async def get_all_balances(self) -> Dict[str, CoinbaseBalance]:
        """
        Get all balances.
        
        Returns:
            Dict[str, CoinbaseBalance]: All balances
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
        request: CoinbaseSpotOrderRequest
    ) -> CoinbaseSpotOrderResponse:
        """
        Place a spot order.
        
        Args:
            request: Order request
            
        Returns:
            CoinbaseSpotOrderResponse: Order response
        """
        try:
            # Convert to CoinbaseOrderRequest
            order_request = CoinbaseOrderRequest(
                product_id=request.product_id,
                side=CoinbaseOrderSide(request.side.value),
                order_type=CoinbaseOrderType(request.order_type.value),
                size=request.size,
                funds=request.funds,
                price=request.price,
                stop_price=request.stop_price,
                time_in_force=CoinbaseTimeInForce(request.time_in_force.value),
                end_time=request.end_time,
                post_only=request.post_only,
                client_order_id=request.client_order_id
            )
            
            # Place order
            order_response = await self.order.place_order(order_request)
            
            # Convert to spot order response
            spot_response = CoinbaseSpotOrderResponse(
                order_id=order_response.order_id,
                client_order_id=order_response.client_order_id,
                product_id=order_response.product_id,
                side=CoinbaseSpotOrderSide(order_response.side.value),
                order_type=CoinbaseSpotOrderType(order_response.order_type.value),
                status=order_response.status,
                price=order_response.price,
                filled_size=order_response.filled_size,
                size=order_response.size,
                funds=order_response.funds,
                filled_funds=order_response.filled_funds,
                time_in_force=CoinbaseSpotTimeInForce(order_response.time_in_force.value),
                stop_price=order_response.stop_price,
                post_only=order_response.post_only,
                created_at=order_response.created_at,
                done_at=order_response.done_at,
                done_reason=order_response.done_reason
            )
            
            logger.info(f"Spot order placed: {spot_response.order_id} for {request.product_id}")
            return spot_response
            
        except Exception as e:
            logger.error(f"Error placing spot order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def place_oco_order(
        self,
        request: CoinbaseOCOOrderRequest
    ) -> CoinbaseOCOOrderResponse:
        """
        Place an OCO order.
        
        Args:
            request: OCO order request
            
        Returns:
            CoinbaseOCOOrderResponse: OCO order response
        """
        try:
            return await self.order.place_oco_order(request)
            
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
            return await self.order.place_bracket_order(request)
            
        except Exception as e:
            logger.error(f"Error placing bracket order: {e}")
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
            return await self.order.cancel_order(order_id)
            
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
            return await self.order.cancel_open_orders(product_id)
            
        except Exception as e:
            logger.error(f"Error cancelling open orders: {e}")
            return 0

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order(self, order_id: str) -> Optional[CoinbaseSpotOrderResponse]:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            
        Returns:
            Optional[CoinbaseSpotOrderResponse]: Order details
        """
        try:
            order_response = await self.order.get_order(order_id)
            if not order_response:
                return None
            
            return CoinbaseSpotOrderResponse(
                order_id=order_response.order_id,
                client_order_id=order_response.client_order_id,
                product_id=order_response.product_id,
                side=CoinbaseSpotOrderSide(order_response.side.value),
                order_type=CoinbaseSpotOrderType(order_response.order_type.value),
                status=order_response.status,
                price=order_response.price,
                filled_size=order_response.filled_size,
                size=order_response.size,
                funds=order_response.funds,
                filled_funds=order_response.filled_funds,
                time_in_force=CoinbaseSpotTimeInForce(order_response.time_in_force.value),
                stop_price=order_response.stop_price,
                post_only=order_response.post_only,
                created_at=order_response.created_at,
                done_at=order_response.done_at,
                done_reason=order_response.done_reason
            )
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    @retry_async(max_attempts=3, delay=0.5)
    async def get_open_orders(self, product_id: Optional[str] = None) -> List[CoinbaseSpotOrderResponse]:
        """
        Get open orders.
        
        Args:
            product_id: Product ID (optional)
            
        Returns:
            List[CoinbaseSpotOrderResponse]: Open orders
        """
        try:
            orders = await self.order.get_open_orders(product_id)
            
            spot_orders = []
            for order in orders:
                spot_orders.append(CoinbaseSpotOrderResponse(
                    order_id=order.order_id,
                    client_order_id=order.client_order_id,
                    product_id=order.product_id,
                    side=CoinbaseSpotOrderSide(order.side.value),
                    order_type=CoinbaseSpotOrderType(order.order_type.value),
                    status=order.status,
                    price=order.price,
                    filled_size=order.filled_size,
                    size=order.size,
                    funds=order.funds,
                    filled_funds=order.filled_funds,
                    time_in_force=CoinbaseSpotTimeInForce(order.time_in_force.value),
                    stop_price=order.stop_price,
                    post_only=order.post_only,
                    created_at=order.created_at,
                    done_at=order.done_at,
                    done_reason=order.done_reason
                ))
            
            return spot_orders
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_ticker(self, product_id: str) -> CoinbaseTicker:
        """Get ticker for product"""
        return await self.market.get_ticker(product_id)

    async def get_candles(
        self,
        product_id: str,
        granularity: CoinbaseGranularity = CoinbaseGranularity.ONE_HOUR,
        limit: int = 500
    ) -> List[CoinbaseCandle]:
        """Get candle data"""
        return await self.market.get_candles(product_id, granularity, limit)

    async def get_order_book(
        self,
        product_id: str,
        level: int = 2
    ) -> CoinbaseOrderBook:
        """Get order book"""
        return await self.market.get_order_book(product_id, level)

    async def get_recent_trades(
        self,
        product_id: str,
        limit: int = 100
    ) -> List[CoinbaseTrade]:
        """Get recent trades"""
        return await self.market.get_recent_trades(product_id, limit)

    # =========================================================================
    # WebSocket Streaming
    # =========================================================================

    async def subscribe(
        self,
        config: CoinbaseSpotStreamConfig,
        websocket: WebSocket
    ) -> None:
        """
        Subscribe to spot market streams.
        
        Args:
            config: Stream configuration
            websocket: WebSocket connection
        """
        stream_config = CoinbaseMarketStreamConfig(
            product_ids=config.product_ids,
            channels=config.channels,
            granularity=config.granularity
        )
        await self.market.subscribe(stream_config, websocket)

    async def unsubscribe(self, stream_key: str) -> None:
        """Unsubscribe from stream"""
        await self.market.unsubscribe(stream_key)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Coinbase spot module"""
        await self.market.close()
        await self.order.close()
        await super().close()
        
        self._account_cache = None
        self._balance_cache.clear()
        
        logger.info("CoinbaseSpot closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/exchanges/coinbase/spot", tags=["Coinbase Spot"])


async def get_spot(
    api_key: str = Query(..., description="Coinbase API Key"),
    api_secret: str = Query(..., description="Coinbase API Secret"),
    passphrase: str = Query(..., description="Coinbase Passphrase"),
    environment: CoinbaseEnvironment = Query(CoinbaseEnvironment.SANDBOX)
) -> CoinbaseSpot:
    """Dependency to get CoinbaseSpot instance"""
    return CoinbaseSpot(api_key, api_secret, passphrase, environment)


@router.get("/account")
async def get_account_info(
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Get spot account information"""
    return await spot.get_account_info()


@router.get("/balance/{currency}")
async def get_balance(
    currency: str,
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Get balance for a currency"""
    return await spot.get_balance(currency)


@router.get("/balances")
async def get_all_balances(
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Get all balances"""
    return await spot.get_all_balances()


@router.post("/order")
async def place_order(
    request: CoinbaseSpotOrderRequest,
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Place a spot order"""
    return await spot.place_order(request)


@router.post("/order/oco")
async def place_oco_order(
    request: CoinbaseOCOOrderRequest,
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Place an OCO order"""
    return await spot.place_oco_order(request)


@router.post("/order/bracket")
async def place_bracket_order(
    request: CoinbaseBracketOrderRequest,
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Place a bracket order"""
    return await spot.place_bracket_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Cancel an order"""
    success = await spot.cancel_order(order_id)
    return {"success": success}


@router.delete("/orders/open")
async def cancel_open_orders(
    product_id: Optional[str] = Query(None),
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Cancel all open orders"""
    count = await spot.cancel_open_orders(product_id)
    return {"cancelled": count}


@router.get("/order/{order_id}")
async def get_order(
    order_id: str,
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Get order details"""
    return await spot.get_order(order_id)


@router.get("/orders/open")
async def get_open_orders(
    product_id: Optional[str] = Query(None),
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Get open orders"""
    return await spot.get_open_orders(product_id)


@router.get("/ticker/{product_id}")
async def get_ticker(
    product_id: str,
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Get ticker for product"""
    return await spot.get_ticker(product_id)


@router.get("/candles/{product_id}")
async def get_candles(
    product_id: str,
    granularity: CoinbaseGranularity = Query(CoinbaseGranularity.ONE_HOUR),
    limit: int = Query(500, le=1000),
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Get candle data"""
    return await spot.get_candles(product_id, granularity, limit)


@router.get("/order-book/{product_id}")
async def get_order_book(
    product_id: str,
    level: int = Query(2, ge=1, le=3),
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Get order book"""
    return await spot.get_order_book(product_id, level)


@router.get("/trades/{product_id}")
async def get_recent_trades(
    product_id: str,
    limit: int = Query(100, le=1000),
    spot: CoinbaseSpot = Depends(get_spot)
):
    """Get recent trades"""
    return await spot.get_recent_trades(product_id, limit)


@router.websocket("/ws/{product_id}")
async def spot_websocket(
    websocket: WebSocket,
    product_id: str,
    channels: List[str] = Query(...),
    spot: CoinbaseSpot = Depends(get_spot)
):
    """WebSocket endpoint for spot market data"""
    await websocket.accept()
    
    config = CoinbaseSpotStreamConfig(
        product_ids=[product_id],
        channels=channels
    )
    
    await spot.subscribe(config, websocket)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await spot.unsubscribe(f"{product_id}_{'_'.join(channels)}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CoinbaseSpot',
    'CoinbaseSpotOrderType',
    'CoinbaseSpotOrderSide',
    'CoinbaseSpotTimeInForce',
    'CoinbaseSpotOrderRequest',
    'CoinbaseSpotOrderResponse',
    'CoinbaseSpotAccountInfo',
    'CoinbaseSpotStreamConfig',
    'router'
]
