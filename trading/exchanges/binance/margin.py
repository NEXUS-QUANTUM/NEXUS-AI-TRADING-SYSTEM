"""
NEXUS AI TRADING SYSTEM - Binance Margin Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/margin.py
Description: Binance margin trading with full API integration
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

class BinanceMarginType(str, Enum):
    """Binance margin types"""
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"


class BinanceMarginOrderType(str, Enum):
    """Binance margin order types"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"


class BinanceMarginOrderSide(str, Enum):
    """Binance margin order sides"""
    BUY = "BUY"
    SELL = "SELL"


class BinanceMarginTimeInForce(str, Enum):
    """Binance margin time in force"""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BinanceMarginAccountInfo(BaseModel):
    """Binance margin account information"""
    account_id: int
    account_type: str
    total_equity: float
    available_balance: float
    margin_used: float
    margin_ratio: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class BinanceMarginPosition(BaseModel):
    """Binance margin position"""
    symbol: str
    position_side: str
    entry_price: float
    mark_price: float
    position_amount: float
    unrealized_pnl: float
    realized_pnl: float
    margin_type: str
    timestamp: datetime


class BinanceMarginOrderRequest(BaseModel):
    """Binance margin order request"""
    symbol: str
    side: BinanceMarginOrderSide
    order_type: BinanceMarginOrderType = BinanceMarginOrderType.LIMIT
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: BinanceMarginTimeInForce = BinanceMarginTimeInForce.GTC
    reduce_only: bool = False
    post_only: bool = False
    client_order_id: Optional[str] = None
    recv_window: int = 5000


class BinanceMarginOrderResponse(BaseModel):
    """Binance margin order response"""
    order_id: int
    client_order_id: str
    symbol: str
    side: BinanceMarginOrderSide
    order_type: BinanceMarginOrderType
    status: str
    price: float
    avg_price: float
    quantity: float
    executed_quantity: float
    cummulative_quote_qty: float
    time_in_force: BinanceMarginTimeInForce
    stop_price: Optional[float] = None
    reduce_only: bool
    post_only: bool
    created_at: datetime
    updated_at: datetime


class BinanceMarginTransferRequest(BaseModel):
    """Binance margin transfer request"""
    asset: str
    amount: float
    transfer_type: str = "MAIN_TO_MARGIN"  # MAIN_TO_MARGIN, MARGIN_TO_MAIN


class BinanceMarginLoanRequest(BaseModel):
    """Binance margin loan request"""
    asset: str
    amount: float
    is_isolated: bool = False
    symbol: Optional[str] = None


class BinanceMarginRepayRequest(BaseModel):
    """Binance margin repay request"""
    asset: str
    amount: float
    is_isolated: bool = False
    symbol: Optional[str] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BinanceMarginStreamConfig:
    """Binance margin stream configuration"""
    symbol: str
    channels: List[str]
    interval: Optional[str] = None
    depth_level: Optional[str] = None


# =============================================================================
# BINANCE MARGIN
# =============================================================================

class BinanceMargin(BinanceBase):
    """
    Binance Margin Trading with full API integration.
    
    Features:
    - Margin trading
    - Position management
    - Margin management
    - Loan management
    - Repay management
    - Order management
    - Market data
    - WebSocket streams
    - Account management
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: BinanceEnvironment = BinanceEnvironment.TESTNET,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BinanceMargin.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            environment: Binance environment
            config: Exchange configuration
        """
        super().__init__(api_key, api_secret, environment, config)
        
        # Error handler
        self._error_handler = BinanceErrorHandler()
        
        # Position cache
        self._position_cache: Dict[str, BinanceMarginPosition] = {}
        
        # Margin cache
        self._margin_cache: Dict[str, Dict[str, Any]] = {}
        
        # Endpoint
        self.margin_endpoint = "/sapi/v1/margin"
        
        logger.info("BinanceMargin initialized")

    # =========================================================================
    # Account Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_account_info(self) -> BinanceMarginAccountInfo:
        """
        Get margin account information.
        
        Returns:
            BinanceMarginAccountInfo: Account information
        """
        try:
            response = await self._request(
                method='GET',
                endpoint=f'{self.margin_endpoint}/account',
                signed=True
            )
            
            return BinanceMarginAccountInfo(
                account_id=response.get('accountId'),
                account_type=response.get('accountType', 'MARGIN'),
                total_equity=float(response.get('totalEquity', 0)),
                available_balance=float(response.get('availableBalance', 0)),
                margin_used=float(response.get('marginUsed', 0)),
                margin_ratio=float(response.get('marginRatio', 0)),
                positions=response.get('userAssets', []),
                orders=response.get('orders', []),
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting margin account info: {e}")
            raise

    # =========================================================================
    # Position Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_positions(self, symbol: Optional[str] = None) -> List[BinanceMarginPosition]:
        """
        Get margin positions.
        
        Args:
            symbol: Symbol (optional)
            
        Returns:
            List[BinanceMarginPosition]: Positions
        """
        try:
            params = {'timestamp': int(time.time() * 1000)}
            
            response = await self._request(
                method='GET',
                endpoint=f'{self.margin_endpoint}/openOrders',
                params=params,
                signed=True
            )
            
            positions = []
            for data in response:
                position = BinanceMarginPosition(
                    symbol=data.get('symbol'),
                    position_side='LONG' if data.get('side') == 'BUY' else 'SHORT',
                    entry_price=float(data.get('price', 0)),
                    mark_price=float(data.get('price', 0)),
                    position_amount=float(data.get('origQty', 0)),
                    unrealized_pnl=0,
                    realized_pnl=0,
                    margin_type='ISOLATED' if data.get('isIsolated', False) else 'CROSS',
                    timestamp=datetime.utcnow()
                )
                positions.append(position)
                
                # Cache
                self._position_cache[position.symbol] = position
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting margin positions: {e}")
            raise

    # =========================================================================
    # Margin Transfer
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def transfer(
        self,
        request: BinanceMarginTransferRequest
    ) -> bool:
        """
        Transfer funds between main and margin account.
        
        Args:
            request: Transfer request
            
        Returns:
            bool: Success indicator
        """
        try:
            params = {
                'asset': request.asset,
                'amount': request.amount,
                'type': 1 if request.transfer_type == "MAIN_TO_MARGIN" else 2,
                'timestamp': int(time.time() * 1000)
            }
            
            await self._request(
                method='POST',
                endpoint=f'{self.margin_endpoint}/transfer',
                params=params,
                signed=True,
                weight=1
            )
            
            logger.info(f"Transfer completed: {request.amount} {request.asset} ({request.transfer_type})")
            return True
            
        except Exception as e:
            logger.error(f"Error transferring funds: {e}")
            return False

    # =========================================================================
    # Margin Loan
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def loan(
        self,
        request: BinanceMarginLoanRequest
    ) -> Dict[str, Any]:
        """
        Borrow assets on margin.
        
        Args:
            request: Loan request
            
        Returns:
            Dict[str, Any]: Loan result
        """
        try:
            params = {
                'asset': request.asset,
                'amount': request.amount,
                'timestamp': int(time.time() * 1000)
            }
            
            if request.is_isolated and request.symbol:
                params['isIsolated'] = 'TRUE'
                params['symbol'] = request.symbol
            
            response = await self._request(
                method='POST',
                endpoint=f'{self.margin_endpoint}/loan',
                params=params,
                signed=True,
                weight=1
            )
            
            logger.info(f"Loan completed: {request.amount} {request.asset}")
            return {
                'asset': request.asset,
                'amount': request.amount,
                'tran_id': response.get('tranId'),
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error borrowing assets: {e}")
            raise

    # =========================================================================
    # Margin Repay
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def repay(
        self,
        request: BinanceMarginRepayRequest
    ) -> Dict[str, Any]:
        """
        Repay borrowed assets.
        
        Args:
            request: Repay request
            
        Returns:
            Dict[str, Any]: Repay result
        """
        try:
            params = {
                'asset': request.asset,
                'amount': request.amount,
                'timestamp': int(time.time() * 1000)
            }
            
            if request.is_isolated and request.symbol:
                params['isIsolated'] = 'TRUE'
                params['symbol'] = request.symbol
            
            response = await self._request(
                method='POST',
                endpoint=f'{self.margin_endpoint}/repay',
                params=params,
                signed=True,
                weight=1
            )
            
            logger.info(f"Repay completed: {request.amount} {request.asset}")
            return {
                'asset': request.asset,
                'amount': request.amount,
                'tran_id': response.get('tranId'),
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error repaying assets: {e}")
            raise

    # =========================================================================
    # Order Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: BinanceMarginOrderRequest
    ) -> BinanceMarginOrderResponse:
        """
        Place a margin order.
        
        Args:
            request: Order request
            
        Returns:
            BinanceMarginOrderResponse: Order response
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
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/api/v3/order',
                params=params,
                signed=True,
                weight=1
            )
            
            # Parse response
            order_response = BinanceMarginOrderResponse(
                order_id=response.get('orderId'),
                client_order_id=response.get('clientOrderId'),
                symbol=response.get('symbol'),
                side=BinanceMarginOrderSide(response.get('side')),
                order_type=BinanceMarginOrderType(response.get('type')),
                status=response.get('status'),
                price=float(response.get('price', 0)),
                avg_price=float(response.get('avgPrice', 0)),
                quantity=float(response.get('origQty', 0)),
                executed_quantity=float(response.get('executedQty', 0)),
                cummulative_quote_qty=float(response.get('cummulativeQuoteQty', 0)),
                time_in_force=BinanceMarginTimeInForce(response.get('timeInForce', 'GTC')),
                stop_price=float(response.get('stopPrice')) if response.get('stopPrice') else None,
                reduce_only=response.get('reduceOnly', False),
                post_only=response.get('postOnly', False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            logger.info(f"Margin order placed: {order_response.order_id} for {request.symbol}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing margin order: {e}")
            raise

    @retry_async(max_attempts=3, delay=0.5)
    async def cancel_order(self, order_id: int, symbol: str) -> bool:
        """
        Cancel a margin order.
        
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
            
            await self._request(
                method='DELETE',
                endpoint='/api/v3/order',
                params=params,
                signed=True,
                weight=1
            )
            
            logger.info(f"Margin order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling margin order: {e}")
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
            
            await self._request(
                method='DELETE',
                endpoint='/api/v3/openOrders',
                params=params,
                signed=True,
                weight=1
            )
            
            logger.info(f"All margin orders cancelled for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return False

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
        """Close the Binance margin connection"""
        await super().close()
        
        self._position_cache.clear()
        self._margin_cache.clear()
        
        logger.info("BinanceMargin closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/binance/margin", tags=["Binance Margin"])


async def get_margin(
    api_key: str = Query(..., description="Binance API Key"),
    api_secret: str = Query(..., description="Binance API Secret"),
    environment: BinanceEnvironment = Query(BinanceEnvironment.TESTNET)
) -> BinanceMargin:
    """Dependency to get BinanceMargin instance"""
    return BinanceMargin(api_key, api_secret, environment)


@router.get("/account")
async def get_account_info(
    margin: BinanceMargin = Depends(get_margin)
):
    """Get margin account information"""
    return await margin.get_account_info()


@router.get("/positions")
async def get_positions(
    symbol: Optional[str] = Query(None),
    margin: BinanceMargin = Depends(get_margin)
):
    """Get margin positions"""
    return await margin.get_positions(symbol)


@router.post("/transfer")
async def transfer(
    request: BinanceMarginTransferRequest,
    margin: BinanceMargin = Depends(get_margin)
):
    """Transfer funds between accounts"""
    return await margin.transfer(request)


@router.post("/loan")
async def loan(
    request: BinanceMarginLoanRequest,
    margin: BinanceMargin = Depends(get_margin)
):
    """Borrow assets on margin"""
    return await margin.loan(request)


@router.post("/repay")
async def repay(
    request: BinanceMarginRepayRequest,
    margin: BinanceMargin = Depends(get_margin)
):
    """Repay borrowed assets"""
    return await margin.repay(request)


@router.post("/order")
async def place_order(
    request: BinanceMarginOrderRequest,
    margin: BinanceMargin = Depends(get_margin)
):
    """Place a margin order"""
    return await margin.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: int,
    symbol: str = Query(..., description="Symbol"),
    margin: BinanceMargin = Depends(get_margin)
):
    """Cancel a margin order"""
    success = await margin.cancel_order(order_id, symbol)
    return {"success": success}


@router.delete("/orders/{symbol}")
async def cancel_all_orders(
    symbol: str,
    margin: BinanceMargin = Depends(get_margin)
):
    """Cancel all open orders for a symbol"""
    success = await margin.cancel_all_orders(symbol)
    return {"success": success}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BinanceMargin',
    'BinanceMarginType',
    'BinanceMarginOrderType',
    'BinanceMarginOrderSide',
    'BinanceMarginTimeInForce',
    'BinanceMarginAccountInfo',
    'BinanceMarginPosition',
    'BinanceMarginOrderRequest',
    'BinanceMarginOrderResponse',
    'BinanceMarginTransferRequest',
    'BinanceMarginLoanRequest',
    'BinanceMarginRepayRequest',
    'BinanceMarginStreamConfig',
    'router'
]
