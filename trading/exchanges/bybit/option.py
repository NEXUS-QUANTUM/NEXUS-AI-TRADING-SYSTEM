"""
NEXUS AI TRADING SYSTEM - Bybit Option Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/option.py
Description: Bybit options trading with full API integration
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

class BybitOptionType(str, Enum):
    """Bybit option types"""
    CALL = "Call"
    PUT = "Put"


class BybitOptionOrderType(str, Enum):
    """Bybit option order types"""
    LIMIT = "Limit"
    MARKET = "Market"
    STOP = "Stop"
    STOP_LIMIT = "StopLimit"
    TAKE_PROFIT = "TakeProfit"
    TAKE_PROFIT_LIMIT = "TakeProfitLimit"


class BybitOptionOrderSide(str, Enum):
    """Bybit option order sides"""
    BUY = "Buy"
    SELL = "Sell"


class BybitOptionTimeInForce(str, Enum):
    """Bybit option time in force"""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "PostOnly"


class BybitOptionOrderStatus(str, Enum):
    """Bybit option order status"""
    CREATED = "Created"
    NEW = "New"
    PARTIALLY_FILLED = "PartiallyFilled"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"
    PENDING_CANCEL = "PendingCancel"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BybitOptionAccountInfo(BaseModel):
    """Bybit option account information"""
    account_id: str
    total_equity: float
    available_balance: float
    used_margin: float
    margin_ratio: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class BybitOptionPosition(BaseModel):
    """Bybit option position"""
    symbol: str
    option_type: BybitOptionType
    strike_price: float
    expiry: datetime
    position_size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    realized_pnl: float
    timestamp: datetime


class BybitOptionOrderRequest(BaseModel):
    """Bybit option order request"""
    symbol: str
    side: BybitOptionOrderSide
    order_type: BybitOptionOrderType = BybitOptionOrderType.LIMIT
    qty: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: BybitOptionTimeInForce = BybitOptionTimeInForce.GTC
    reduce_only: bool = False
    close_on_trigger: bool = False
    order_link_id: Optional[str] = None


class BybitOptionOrderResponse(BaseModel):
    """Bybit option order response"""
    order_id: str
    order_link_id: str
    symbol: str
    side: BybitOptionOrderSide
    order_type: BybitOptionOrderType
    status: BybitOptionOrderStatus
    price: float
    avg_price: float
    qty: float
    cum_exec_qty: float
    cum_exec_value: float
    time_in_force: BybitOptionTimeInForce
    stop_price: Optional[float] = None
    reduce_only: bool
    close_on_trigger: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BybitOptionStreamConfig:
    """Bybit option stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BYBIT OPTION
# =============================================================================

class BybitOption(BybitBase):
    """
    Bybit Options Trading with full API integration.
    
    Features:
    - Options trading (calls and puts)
    - Position management
    - Order management
    - Market data
    - WebSocket streams
    - Account management
    - Risk management
    - Greeks calculation
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: BybitEnvironment = BybitEnvironment.TESTNET,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BybitOption.
        
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
            BybitCategory.OPTION,
            config
        )
        
        # Error handler
        self._error_handler = BybitErrorHandler()
        
        # Position cache
        self._position_cache: Dict[str, BybitOptionPosition] = {}
        
        # Greeks cache
        self._greeks_cache: Dict[str, Dict[str, float]] = {}
        
        logger.info("BybitOption initialized")

    # =========================================================================
    # Account Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_account_info(self) -> BybitOptionAccountInfo:
        """
        Get option account information.
        
        Returns:
            BybitOptionAccountInfo: Account information
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/v5/account/info',
                signed=True
            )
            
            data = response
            
            return BybitOptionAccountInfo(
                account_id=data.get('accountId', ''),
                total_equity=float(data.get('totalEquity', 0)),
                available_balance=float(data.get('availableBalance', 0)),
                used_margin=float(data.get('usedMargin', 0)),
                margin_ratio=float(data.get('marginRatio', 0)),
                positions=data.get('positions', []),
                orders=data.get('orders', []),
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting option account info: {e}")
            raise

    # =========================================================================
    # Position Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_positions(self, symbol: Optional[str] = None) -> List[BybitOptionPosition]:
        """
        Get option positions.
        
        Args:
            symbol: Symbol (optional)
            
        Returns:
            List[BybitOptionPosition]: Positions
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
                position = BybitOptionPosition(
                    symbol=data.get('symbol'),
                    option_type=BybitOptionType(data.get('optionType', 'Call')),
                    strike_price=float(data.get('strikePrice', 0)),
                    expiry=datetime.fromtimestamp(int(data.get('expiry', 0)) / 1000),
                    position_size=float(data.get('size', 0)),
                    entry_price=float(data.get('avgPrice', 0)),
                    mark_price=float(data.get('markPrice', 0)),
                    unrealized_pnl=float(data.get('unrealisedPnl', 0)),
                    realized_pnl=float(data.get('realisedPnl', 0)),
                    timestamp=datetime.utcnow()
                )
                positions.append(position)
                
                # Cache
                self._position_cache[position.symbol] = position
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting option positions: {e}")
            raise

    # =========================================================================
    # Order Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: BybitOptionOrderRequest
    ) -> BybitOptionOrderResponse:
        """
        Place an option order.
        
        Args:
            request: Order request
            
        Returns:
            BybitOptionOrderResponse: Order response
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
            
            if request.order_link_id:
                data['orderLinkId'] = request.order_link_id
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/v5/order/create',
                data=data,
                signed=True
            )
            
            result = response
            
            # Parse response
            order_response = BybitOptionOrderResponse(
                order_id=result.get('orderId'),
                order_link_id=result.get('orderLinkId', ''),
                symbol=result.get('symbol'),
                side=BybitOptionOrderSide(result.get('side')),
                order_type=BybitOptionOrderType(result.get('orderType')),
                status=BybitOptionOrderStatus(result.get('orderStatus')),
                price=float(result.get('price', 0)),
                avg_price=float(result.get('avgPrice', 0)),
                qty=float(result.get('qty', 0)),
                cum_exec_qty=float(result.get('cumExecQty', 0)),
                cum_exec_value=float(result.get('cumExecValue', 0)),
                time_in_force=BybitOptionTimeInForce(result.get('timeInForce', 'GTC')),
                stop_price=float(result.get('stopPrice')) if result.get('stopPrice') else None,
                reduce_only=result.get('reduceOnly', False),
                close_on_trigger=result.get('closeOnTrigger', False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            logger.info(f"Option order placed: {order_response.order_id} for {request.symbol}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing option order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an option order.
        
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
            
            logger.info(f"Option order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling option order: {e}")
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
            
            logger.info(f"All option orders cancelled for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return False

    # =========================================================================
    # Greeks Calculation
    # =========================================================================

    async def calculate_greeks(
        self,
        symbol: str,
        price: float,
        strike: float,
        expiry: datetime,
        option_type: BybitOptionType,
        volatility: float = 0.3,
        risk_free_rate: float = 0.03
    ) -> Dict[str, float]:
        """
        Calculate option Greeks.
        
        Args:
            symbol: Symbol
            price: Underlying price
            strike: Strike price
            expiry: Expiry date
            option_type: Option type (Call/Put)
            volatility: Implied volatility
            risk_free_rate: Risk-free rate
            
        Returns:
            Dict[str, float]: Greeks (delta, gamma, theta, vega, rho)
        """
        try:
            from scipy.stats import norm
            import numpy as np
            
            # Calculate time to expiry in years
            T = (expiry - datetime.utcnow()).total_seconds() / (365 * 24 * 3600)
            T = max(T, 0.001)  # Minimum 1 day
            
            d1 = (np.log(price / strike) + (risk_free_rate + 0.5 * volatility ** 2) * T) / (volatility * np.sqrt(T))
            d2 = d1 - volatility * np.sqrt(T)
            
            if option_type == BybitOptionType.CALL:
                delta = norm.cdf(d1)
                gamma = norm.pdf(d1) / (price * volatility * np.sqrt(T))
                theta = -(price * volatility * norm.pdf(d1)) / (2 * np.sqrt(T)) - risk_free_rate * strike * np.exp(-risk_free_rate * T) * norm.cdf(d2)
                vega = price * np.sqrt(T) * norm.pdf(d1) / 100
                rho = strike * T * np.exp(-risk_free_rate * T) * norm.cdf(d2) / 100
            else:  # PUT
                delta = -norm.cdf(-d1)
                gamma = norm.pdf(d1) / (price * volatility * np.sqrt(T))
                theta = -(price * volatility * norm.pdf(d1)) / (2 * np.sqrt(T)) + risk_free_rate * strike * np.exp(-risk_free_rate * T) * norm.cdf(-d2)
                vega = price * np.sqrt(T) * norm.pdf(d1) / 100
                rho = -strike * T * np.exp(-risk_free_rate * T) * norm.cdf(-d2) / 100
            
            greeks = {
                'delta': float(delta),
                'gamma': float(gamma),
                'theta': float(theta * 365),  # Annualized
                'vega': float(vega),
                'rho': float(rho / 100),
                'd1': float(d1),
                'd2': float(d2)
            }
            
            # Cache
            self._greeks_cache[symbol] = greeks
            
            return greeks
            
        except Exception as e:
            logger.error(f"Error calculating Greeks: {e}")
            return {
                'delta': 0,
                'gamma': 0,
                'theta': 0,
                'vega': 0,
                'rho': 0,
                'd1': 0,
                'd2': 0
            }

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_option_chain(self, symbol: str) -> Dict[str, Any]:
        """
        Get option chain for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            Dict[str, Any]: Option chain data
        """
        try:
            params = {'symbol': symbol}
            
            response = await self._request(
                method='GET',
                endpoint='/v5/market/option-chain',
                params=params
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
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
        """Close the Bybit option connection"""
        await super().close()
        
        self._position_cache.clear()
        self._greeks_cache.clear()
        
        logger.info("BybitOption closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/bybit/option", tags=["Bybit Option"])


async def get_option(
    api_key: str = Query(..., description="Bybit API Key"),
    api_secret: str = Query(..., description="Bybit API Secret"),
    environment: BybitEnvironment = Query(BybitEnvironment.TESTNET)
) -> BybitOption:
    """Dependency to get BybitOption instance"""
    return BybitOption(api_key, api_secret, environment)


@router.get("/account")
async def get_account_info(
    option: BybitOption = Depends(get_option)
):
    """Get option account information"""
    return await option.get_account_info()


@router.get("/positions")
async def get_positions(
    symbol: Optional[str] = Query(None),
    option: BybitOption = Depends(get_option)
):
    """Get option positions"""
    return await option.get_positions(symbol)


@router.post("/order")
async def place_order(
    request: BybitOptionOrderRequest,
    option: BybitOption = Depends(get_option)
):
    """Place an option order"""
    return await option.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    symbol: str = Query(..., description="Symbol"),
    option: BybitOption = Depends(get_option)
):
    """Cancel an option order"""
    success = await option.cancel_order(order_id, symbol)
    return {"success": success}


@router.delete("/orders/{symbol}")
async def cancel_all_orders(
    symbol: str,
    option: BybitOption = Depends(get_option)
):
    """Cancel all open orders for a symbol"""
    success = await option.cancel_all_orders(symbol)
    return {"success": success}


@router.post("/greeks")
async def calculate_greeks(
    symbol: str = Body(..., embed=True),
    price: float = Body(..., embed=True),
    strike: float = Body(..., embed=True),
    expiry: datetime = Body(..., embed=True),
    option_type: BybitOptionType = Body(..., embed=True),
    volatility: float = Body(0.3, embed=True),
    risk_free_rate: float = Body(0.03, embed=True),
    option: BybitOption = Depends(get_option)
):
    """Calculate option Greeks"""
    return await option.calculate_greeks(
        symbol, price, strike, expiry, option_type, volatility, risk_free_rate
    )


@router.get("/chain/{symbol}")
async def get_option_chain(
    symbol: str,
    option: BybitOption = Depends(get_option)
):
    """Get option chain"""
    return await option.get_option_chain(symbol)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitOption',
    'BybitOptionType',
    'BybitOptionOrderType',
    'BybitOptionOrderSide',
    'BybitOptionTimeInForce',
    'BybitOptionOrderStatus',
    'BybitOptionAccountInfo',
    'BybitOptionPosition',
    'BybitOptionOrderRequest',
    'BybitOptionOrderResponse',
    'BybitOptionStreamConfig',
    'router'
]
