"""
NEXUS AI TRADING SYSTEM - Binance Futures Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/futures.py
Description: Binance futures trading with full API integration
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
from trading.exchanges.binance.account import BinanceAccount, BinanceCredentials
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

class BinanceFuturesType(str, Enum):
    """Binance futures types"""
    USD_M = "USD-M"  # USD Margined (Linear)
    COIN_M = "COIN-M"  # Coin Margined (Inverse)


class BinanceFuturesOrderType(str, Enum):
    """Binance futures order types"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"


class BinanceFuturesOrderSide(str, Enum):
    """Binance futures order sides"""
    BUY = "BUY"
    SELL = "SELL"


class BinanceFuturesPositionSide(str, Enum):
    """Binance futures position sides"""
    BOTH = "BOTH"
    LONG = "LONG"
    SHORT = "SHORT"


class BinanceFuturesWorkingType(str, Enum):
    """Binance futures working types"""
    MARK_PRICE = "MARK_PRICE"
    CONTRACT_PRICE = "CONTRACT_PRICE"


class BinanceFuturesTimeInForce(str, Enum):
    """Binance futures time in force"""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    GTX = "GTX"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BinanceFuturesAccountInfo(BaseModel):
    """Binance futures account information"""
    account_id: int
    can_trade: bool
    can_withdraw: bool
    can_deposit: bool
    total_equity: float
    available_balance: float
    margin_used: float
    margin_ratio: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class BinanceFuturesPosition(BaseModel):
    """Binance futures position"""
    symbol: str
    position_side: BinanceFuturesPositionSide
    entry_price: float
    mark_price: float
    position_amount: float
    unrealized_pnl: float
    realized_pnl: float
    leverage: int
    liquidation_price: float
    margin_type: str
    timestamp: datetime


class BinanceFuturesOrderRequest(BaseModel):
    """Binance futures order request"""
    symbol: str
    side: BinanceFuturesOrderSide
    position_side: BinanceFuturesPositionSide = BinanceFuturesPositionSide.BOTH
    order_type: BinanceFuturesOrderType = BinanceFuturesOrderType.LIMIT
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: BinanceFuturesTimeInForce = BinanceFuturesTimeInForce.GTC
    reduce_only: bool = False
    working_type: BinanceFuturesWorkingType = BinanceFuturesWorkingType.CONTRACT_PRICE
    client_order_id: Optional[str] = None
    recv_window: int = 5000


class BinanceFuturesOrderResponse(BaseModel):
    """Binance futures order response"""
    order_id: int
    client_order_id: str
    symbol: str
    side: BinanceFuturesOrderSide
    position_side: BinanceFuturesPositionSide
    order_type: BinanceFuturesOrderType
    status: str
    price: float
    avg_price: float
    quantity: float
    executed_quantity: float
    cum_quote: float
    time_in_force: BinanceFuturesTimeInForce
    reduce_only: bool
    stop_price: Optional[float] = None
    working_type: BinanceFuturesWorkingType
    created_at: datetime
    updated_at: datetime


class BinanceFuturesLeverageRequest(BaseModel):
    """Binance futures leverage request"""
    symbol: str
    leverage: int = 1
    margin_type: str = "ISOLATED"  # ISOLATED, CROSS


class BinanceFuturesMarginTypeRequest(BaseModel):
    """Binance futures margin type request"""
    symbol: str
    margin_type: str = "ISOLATED"  # ISOLATED, CROSS


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BinanceFuturesStreamConfig:
    """Binance futures stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BINANCE FUTURES
# =============================================================================

class BinanceFutures(BinanceBase):
    """
    Binance Futures Trading with full API integration.
    
    Features:
    - Futures trading
    - Position management
    - Leverage management
    - Margin management
    - Order management
    - Market data
    - WebSocket streams
    - Account management
    - Risk management
    """

    FUTURES_BASE_URL = "https://fapi.binance.com"
    FUTURES_TESTNET_BASE_URL = "https://testnet.binancefuture.com"
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: BinanceEnvironment = BinanceEnvironment.TESTNET,
        futures_type: BinanceFuturesType = BinanceFuturesType.USD_M,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BinanceFutures.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            environment: Binance environment
            futures_type: Futures type
            config: Exchange configuration
        """
        super().__init__(api_key, api_secret, environment, config)
        
        self.futures_type = futures_type
        
        # Base URL
        if environment == BinanceEnvironment.TESTNET:
            self.base_url = self.FUTURES_TESTNET_BASE_URL
        else:
            self.base_url = self.FUTURES_BASE_URL
        
        # Error handler
        self._error_handler = BinanceErrorHandler()
        
        # Position cache
        self._position_cache: Dict[str, BinanceFuturesPosition] = {}
        
        # Leverage cache
        self._leverage_cache: Dict[str, int] = {}
        
        logger.info(f"BinanceFutures initialized for {futures_type.value}")

    # =========================================================================
    # Account Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_account_info(self) -> BinanceFuturesAccountInfo:
        """
        Get futures account information.
        
        Returns:
            BinanceFuturesAccountInfo: Account information
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/fapi/v2/account',
                signed=True
            )
            
            # Parse response
            return BinanceFuturesAccountInfo(
                account_id=response.get('accountId'),
                can_trade=response.get('canTrade', False),
                can_withdraw=response.get('canWithdraw', False),
                can_deposit=response.get('canDeposit', False),
                total_equity=float(response.get('totalEquity', 0)),
                available_balance=float(response.get('availableBalance', 0)),
                margin_used=float(response.get('totalMarginUsed', 0)),
                margin_ratio=float(response.get('totalMarginRatio', 0)),
                positions=response.get('positions', []),
                orders=response.get('orders', []),
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting futures account info: {e}")
            raise

    # =========================================================================
    # Position Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_positions(self, symbol: Optional[str] = None) -> List[BinanceFuturesPosition]:
        """
        Get futures positions.
        
        Args:
            symbol: Symbol (optional)
            
        Returns:
            List[BinanceFuturesPosition]: Positions
        """
        try:
            params = {'timestamp': int(time.time() * 1000)}
            if symbol:
                params['symbol'] = symbol
            
            response = await self._request(
                method='GET',
                endpoint='/fapi/v2/positionRisk',
                params=params,
                signed=True
            )
            
            positions = []
            for data in response:
                position = BinanceFuturesPosition(
                    symbol=data.get('symbol'),
                    position_side=BinanceFuturesPositionSide(data.get('positionSide', 'BOTH')),
                    entry_price=float(data.get('entryPrice', 0)),
                    mark_price=float(data.get('markPrice', 0)),
                    position_amount=float(data.get('positionAmt', 0)),
                    unrealized_pnl=float(data.get('unrealizedProfit', 0)),
                    realized_pnl=float(data.get('realizedProfit', 0)),
                    leverage=int(data.get('leverage', 1)),
                    liquidation_price=float(data.get('liquidationPrice', 0)),
                    margin_type=data.get('marginType', 'ISOLATED'),
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
        margin_type: str = "ISOLATED"
    ) -> bool:
        """
        Set leverage for a symbol.
        
        Args:
            symbol: Symbol
            leverage: Leverage (1-125)
            margin_type: Margin type (ISOLATED, CROSS)
            
        Returns:
            bool: Success indicator
        """
        try:
            # Set margin type
            if margin_type.upper() not in ['ISOLATED', 'CROSS']:
                raise ValueError("Margin type must be ISOLATED or CROSS")
            
            # Set margin type first
            margin_params = {
                'symbol': symbol,
                'marginType': margin_type.upper(),
                'timestamp': int(time.time() * 1000)
            }
            
            await self._request(
                method='POST',
                endpoint='/fapi/v1/marginType',
                params=margin_params,
                signed=True,
                weight=1
            )
            
            # Set leverage
            leverage_params = {
                'symbol': symbol,
                'leverage': leverage,
                'timestamp': int(time.time() * 1000)
            }
            
            await self._request(
                method='POST',
                endpoint='/fapi/v1/leverage',
                params=leverage_params,
                signed=True,
                weight=1
            )
            
            # Cache
            self._leverage_cache[symbol] = leverage
            
            logger.info(f"Leverage set for {symbol}: {leverage}x ({margin_type})")
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
        request: BinanceFuturesOrderRequest
    ) -> BinanceFuturesOrderResponse:
        """
        Place a futures order.
        
        Args:
            request: Order request
            
        Returns:
            BinanceFuturesOrderResponse: Order response
        """
        try:
            # Prepare order parameters
            params = {
                'symbol': request.symbol,
                'side': request.side.value,
                'positionSide': request.position_side.value,
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
            
            if request.working_type:
                params['workingType'] = request.working_type.value
            
            if request.client_order_id:
                params['newClientOrderId'] = request.client_order_id
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/fapi/v1/order',
                params=params,
                signed=True,
                weight=1
            )
            
            # Parse response
            order_response = BinanceFuturesOrderResponse(
                order_id=response.get('orderId'),
                client_order_id=response.get('clientOrderId'),
                symbol=response.get('symbol'),
                side=BinanceFuturesOrderSide(response.get('side')),
                position_side=BinanceFuturesPositionSide(response.get('positionSide', 'BOTH')),
                order_type=BinanceFuturesOrderType(response.get('type')),
                status=response.get('status'),
                price=float(response.get('price', 0)),
                avg_price=float(response.get('avgPrice', 0)),
                quantity=float(response.get('origQty', 0)),
                executed_quantity=float(response.get('executedQty', 0)),
                cum_quote=float(response.get('cumQuote', 0)),
                time_in_force=BinanceFuturesTimeInForce(response.get('timeInForce', 'GTC')),
                reduce_only=response.get('reduceOnly', False),
                stop_price=float(response.get('stopPrice')) if response.get('stopPrice') else None,
                working_type=BinanceFuturesWorkingType(response.get('workingType', 'CONTRACT_PRICE')),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Update position cache
            await self._update_position_cache(request.symbol)
            
            logger.info(f"Futures order placed: {order_response.order_id} for {request.symbol}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing futures order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_order(self, order_id: int, symbol: str) -> bool:
        """
        Cancel a futures order.
        
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
                endpoint='/fapi/v1/order',
                params=params,
                signed=True,
                weight=1
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
            params = {
                'symbol': symbol,
                'timestamp': int(time.time() * 1000)
            }
            
            response = await self._request(
                method='DELETE',
                endpoint='/fapi/v1/allOpenOrders',
                params=params,
                signed=True,
                weight=1
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
            response = await self._request(
                method='GET',
                endpoint='/fapi/v1/fundingRate',
                params={'symbol': symbol}
            )
            
            if response:
                return {
                    'symbol': symbol,
                    'funding_rate': float(response[0].get('fundingRate', 0)),
                    'funding_time': datetime.fromtimestamp(response[0].get('fundingTime', 0) / 1000),
                    'next_funding_time': datetime.fromtimestamp(response[1].get('fundingTime', 0) / 1000) if len(response) > 1 else None
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
            response = await self._request(
                method='GET',
                endpoint='/fapi/v1/premiumIndex',
                params={'symbol': symbol}
            )
            
            return {
                'symbol': response.get('symbol'),
                'mark_price': float(response.get('markPrice', 0)),
                'index_price': float(response.get('indexPrice', 0)),
                'last_funding_rate': float(response.get('lastFundingRate', 0)),
                'next_funding_time': datetime.fromtimestamp(response.get('nextFundingTime', 0) / 1000),
                'timestamp': datetime.utcnow()
            }
            
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
        """Close the Binance futures connection"""
        await super().close()
        
        self._position_cache.clear()
        self._leverage_cache.clear()
        
        logger.info("BinanceFutures closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/binance/futures", tags=["Binance Futures"])


async def get_futures(
    api_key: str = Query(..., description="Binance API Key"),
    api_secret: str = Query(..., description="Binance API Secret"),
    environment: BinanceEnvironment = Query(BinanceEnvironment.TESTNET),
    futures_type: BinanceFuturesType = Query(BinanceFuturesType.USD_M)
) -> BinanceFutures:
    """Dependency to get BinanceFutures instance"""
    return BinanceFutures(api_key, api_secret, environment, futures_type)


@router.get("/account")
async def get_account_info(
    futures: BinanceFutures = Depends(get_futures)
):
    """Get futures account information"""
    return await futures.get_account_info()


@router.get("/positions")
async def get_positions(
    symbol: Optional[str] = Query(None),
    futures: BinanceFutures = Depends(get_futures)
):
    """Get futures positions"""
    return await futures.get_positions(symbol)


@router.post("/leverage")
async def set_leverage(
    request: BinanceFuturesLeverageRequest,
    futures: BinanceFutures = Depends(get_futures)
):
    """Set leverage for a symbol"""
    return await futures.set_leverage(request.symbol, request.leverage, request.margin_type)


@router.get("/leverage/{symbol}")
async def get_leverage(
    symbol: str,
    futures: BinanceFutures = Depends(get_futures)
):
    """Get leverage for a symbol"""
    return await futures.get_leverage(symbol)


@router.post("/order")
async def place_order(
    request: BinanceFuturesOrderRequest,
    futures: BinanceFutures = Depends(get_futures)
):
    """Place a futures order"""
    return await futures.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: int,
    symbol: str = Query(..., description="Symbol"),
    futures: BinanceFutures = Depends(get_futures)
):
    """Cancel a futures order"""
    success = await futures.cancel_order(order_id, symbol)
    return {"success": success}


@router.delete("/orders/{symbol}")
async def cancel_all_orders(
    symbol: str,
    futures: BinanceFutures = Depends(get_futures)
):
    """Cancel all open orders for a symbol"""
    success = await futures.cancel_all_orders(symbol)
    return {"success": success}


@router.get("/funding-rate/{symbol}")
async def get_funding_rate(
    symbol: str,
    futures: BinanceFutures = Depends(get_futures)
):
    """Get funding rate for a symbol"""
    return await futures.get_funding_rate(symbol)


@router.get("/mark-price/{symbol}")
async def get_mark_price(
    symbol: str,
    futures: BinanceFutures = Depends(get_futures)
):
    """Get mark price for a symbol"""
    return await futures.get_mark_price(symbol)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BinanceFutures',
    'BinanceFuturesType',
    'BinanceFuturesOrderType',
    'BinanceFuturesOrderSide',
    'BinanceFuturesPositionSide',
    'BinanceFuturesWorkingType',
    'BinanceFuturesTimeInForce',
    'BinanceFuturesAccountInfo',
    'BinanceFuturesPosition',
    'BinanceFuturesOrderRequest',
    'BinanceFuturesOrderResponse',
    'BinanceFuturesLeverageRequest',
    'BinanceFuturesMarginTypeRequest',
    'BinanceFuturesStreamConfig',
    'router'
]
