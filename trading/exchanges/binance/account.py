"""
NEXUS AI TRADING SYSTEM - Binance Account Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/account.py
Description: Binance exchange account management with full API integration
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
import requests
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.exchange_config import ExchangeConfig
from shared.constants.trading_constants import ORDER_TYPES, POSITION_DIRECTIONS
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BinanceAccountType(str, Enum):
    """Binance account types"""
    SPOT = "spot"
    MARGIN = "margin"
    FUTURES = "futures"
    ISOLATED = "isolated"


class BinanceOrderStatus(str, Enum):
    """Binance order status"""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PENDING_CANCEL = "PENDING_CANCEL"


class BinanceOrderType(str, Enum):
    """Binance order types"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"


class BinanceOrderSide(str, Enum):
    """Binance order sides"""
    BUY = "BUY"
    SELL = "SELL"


class BinanceTimeInForce(str, Enum):
    """Binance time in force"""
    GTC = "GTC"  # Good till cancelled
    IOC = "IOC"  # Immediate or cancel
    FOK = "FOK"  # Fill or kill


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BinanceAccountInfo(BaseModel):
    """Binance account information"""
    account_id: str
    account_type: BinanceAccountType
    balance: Dict[str, float]
    total_balance_usd: float
    available_balance_usd: float
    margin_used_usd: float
    margin_ratio: float
    leverage: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class BinanceBalance(BaseModel):
    """Binance balance"""
    asset: str
    free: float
    locked: float
    total: float


class BinanceOrderRequest(BaseModel):
    """Binance order request"""
    symbol: str
    side: BinanceOrderSide
    order_type: BinanceOrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: BinanceTimeInForce = BinanceTimeInForce.GTC
    reduce_only: bool = False
    post_only: bool = False
    client_order_id: Optional[str] = None
    recv_window: int = 5000
    new_order_resp_type: str = "FULL"


class BinanceOrderResponse(BaseModel):
    """Binance order response"""
    order_id: int
    client_order_id: str
    symbol: str
    side: BinanceOrderSide
    order_type: BinanceOrderType
    status: BinanceOrderStatus
    price: float
    avg_price: float
    quantity: float
    executed_quantity: float
    cummulative_quote_qty: float
    time_in_force: BinanceTimeInForce
    stop_price: Optional[float] = None
    reduce_only: bool
    post_only: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BinanceCredentials:
    """Binance API credentials"""
    api_key: str
    api_secret: str
    testnet: bool = False


@dataclass
class BinanceApiResponse:
    """Binance API response"""
    status: int
    data: Dict[str, Any]
    error: Optional[str] = None


# =============================================================================
# BINANCE ACCOUNT
# =============================================================================

class BinanceAccount:
    """
    Binance Exchange Account Management with full API integration.
    
    Features:
    - Account information
    - Balance management
    - Order placement and management
    - Position management
    - Margin management
    - API authentication
    - Rate limiting
    - Error handling
    - Testnet support
    """

    BASE_URL = "https://api.binance.com"
    TESTNET_BASE_URL = "https://testnet.binance.vision"
    
    def __init__(
        self,
        credentials: BinanceCredentials,
        account_type: BinanceAccountType = BinanceAccountType.SPOT,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BinanceAccount.
        
        Args:
            credentials: Binance API credentials
            account_type: Binance account type
            config: Exchange configuration
        """
        self.credentials = credentials
        self.account_type = account_type
        self.config = config or ExchangeConfig()
        
        # Base URL
        self.base_url = self.TESTNET_BASE_URL if credentials.testnet else self.BASE_URL
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting
        self._rate_limit: Dict[str, Any] = {
            'requests_per_minute': 1200,
            'requests': [],
            'last_reset': datetime.utcnow()
        }
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Order cache
        self._order_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"BinanceAccount initialized for {account_type.value}")

    # =========================================================================
    # Session Management
    # =========================================================================

    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession(
            headers={
                'X-MBX-APIKEY': self.credentials.api_key,
                'Content-Type': 'application/json'
            },
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
            self._session = None

    # =========================================================================
    # API Request Methods
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0, backoff=2.0)
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> BinanceApiResponse:
        """
        Make an API request to Binance.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request data
            signed: Whether request requires signing
            
        Returns:
            BinanceApiResponse: API response
        """
        try:
            # Check rate limit
            await self._check_rate_limit()
            
            # Prepare request
            url = f"{self.base_url}{endpoint}"
            headers = {}
            
            # Add signature if required
            if signed:
                params = params or {}
                params['timestamp'] = int(time.time() * 1000)
                params['recvWindow'] = params.get('recvWindow', 5000)
                
                # Sort parameters
                query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                signature = hmac.new(
                    self.credentials.api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                params['signature'] = signature
            
            # Make request
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers
            ) as response:
                # Update rate limit
                self._update_rate_limit()
                
                # Parse response
                response_data = await response.json()
                
                if response.status >= 400:
                    return BinanceApiResponse(
                        status=response.status,
                        data={},
                        error=response_data.get('msg', 'Unknown error')
                    )
                
                return BinanceApiResponse(
                    status=response.status,
                    data=response_data
                )
                
        except asyncio.TimeoutError:
            return BinanceApiResponse(
                status=408,
                data={},
                error="Request timeout"
            )
        except Exception as e:
            logger.error(f"API request error: {e}")
            return BinanceApiResponse(
                status=500,
                data={},
                error=str(e)
            )

    async def _check_rate_limit(self) -> None:
        """Check if rate limit is exceeded"""
        now = datetime.utcnow()
        
        # Reset rate limit if minute has passed
        if (now - self._rate_limit['last_reset']).seconds >= 60:
            self._rate_limit['requests'] = []
            self._rate_limit['last_reset'] = now
        
        # Check if limit exceeded
        if len(self._rate_limit['requests']) >= self._rate_limit['requests_per_minute']:
            await asyncio.sleep(1)
            await self._check_rate_limit()

    def _update_rate_limit(self) -> None:
        """Update rate limit tracking"""
        self._rate_limit['requests'].append(datetime.utcnow())

    # =========================================================================
    # Account Information
    # =========================================================================

    async def get_account_info(self) -> BinanceAccountInfo:
        """
        Get account information.
        
        Returns:
            BinanceAccountInfo: Account information
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/api/v3/account',
                signed=True
            )
            
            if response.error:
                raise Exception(response.error)
            
            data = response.data
            
            # Parse balances
            balances = {}
            total_balance = 0
            available_balance = 0
            
            for balance in data.get('balances', []):
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                if total > 0:
                    balances[asset] = {
                        'free': free,
                        'locked': locked,
                        'total': total
                    }
                    
                    # Get price for USD value
                    price = await self._get_price(asset)
                    if price:
                        total_balance += total * price
                        available_balance += free * price
            
            return BinanceAccountInfo(
                account_id=data.get('accountId'),
                account_type=self.account_type,
                balance=balances,
                total_balance_usd=total_balance,
                available_balance_usd=available_balance,
                margin_used_usd=0,  # Would calculate from positions
                margin_ratio=0,
                leverage=1.0,
                positions=[],  # Would fetch from positions endpoint
                orders=[],  # Would fetch from orders endpoint
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            raise

    async def _get_price(self, asset: str) -> Optional[float]:
        """Get price of asset in USD"""
        try:
            if asset == 'USDT':
                return 1.0
            
            symbol = f"{asset}USDT"
            response = await self._request(
                method='GET',
                endpoint='/api/v3/ticker/price',
                params={'symbol': symbol}
            )
            
            if response.data:
                return float(response.data.get('price', 0))
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting price for {asset}: {e}")
            return None

    # =========================================================================
    # Balance Management
    # =========================================================================

    async def get_balance(self, asset: str) -> Optional[BinanceBalance]:
        """
        Get balance for an asset.
        
        Args:
            asset: Asset symbol
            
        Returns:
            Optional[BinanceBalance]: Balance
        """
        try:
            account = await self.get_account_info()
            
            if asset in account.balance:
                balance = account.balance[asset]
                return BinanceBalance(
                    asset=asset,
                    free=balance['free'],
                    locked=balance['locked'],
                    total=balance['total']
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting balance for {asset}: {e}")
            return None

    async def get_all_balances(self) -> Dict[str, BinanceBalance]:
        """
        Get all balances.
        
        Returns:
            Dict[str, BinanceBalance]: All balances
        """
        try:
            account = await self.get_account_info()
            balances = {}
            
            for asset, balance in account.balance.items():
                balances[asset] = BinanceBalance(
                    asset=asset,
                    free=balance['free'],
                    locked=balance['locked'],
                    total=balance['total']
                )
            
            return balances
            
        except Exception as e:
            logger.error(f"Error getting all balances: {e}")
            return {}

    # =========================================================================
    # Order Management
    # =========================================================================

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
                signed=True
            )
            
            if response.error:
                raise Exception(response.error)
            
            data = response.data
            
            # Parse response
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
            
            # Cache order
            self._order_cache[str(order_response.order_id)] = order_response.dict()
            
            logger.info(f"Order placed: {order_response.order_id} for {request.symbol}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

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
            params = {
                'symbol': symbol,
                'orderId': order_id,
                'timestamp': int(time.time() * 1000)
            }
            
            response = await self._request(
                method='DELETE',
                endpoint='/api/v3/order',
                params=params,
                signed=True
            )
            
            if response.error:
                raise Exception(response.error)
            
            # Remove from cache
            if str(order_id) in self._order_cache:
                del self._order_cache[str(order_id)]
            
            logger.info(f"Order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

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
            if str(order_id) in self._order_cache:
                cached = self._order_cache[str(order_id)]
                return BinanceOrderResponse(**cached)
            
            params = {
                'symbol': symbol,
                'orderId': order_id,
                'timestamp': int(time.time() * 1000)
            }
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/order',
                params=params,
                signed=True
            )
            
            if response.error:
                raise Exception(response.error)
            
            data = response.data
            
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
            
            # Cache order
            self._order_cache[str(order_response.order_id)] = order_response.dict()
            
            return order_response
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    async def get_open_orders(self, symbol: str) -> List[BinanceOrderResponse]:
        """
        Get open orders.
        
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
                signed=True
            )
            
            if response.error:
                raise Exception(response.error)
            
            orders = []
            for data in response.data:
                orders.append(BinanceOrderResponse(
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
                ))
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []

    # =========================================================================
    # Position Management
    # =========================================================================

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get positions.
        
        Returns:
            List[Dict[str, Any]]: Positions
        """
        try:
            # For spot, positions are just balances
            account = await self.get_account_info()
            positions = []
            
            for asset, balance in account.balance.items():
                if balance['total'] > 0:
                    positions.append({
                        'asset': asset,
                        'size': balance['total'],
                        'free': balance['free'],
                        'locked': balance['locked'],
                        'value_usd': balance['total'] * (await self._get_price(asset) or 0)
                    })
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Binance account connection"""
        if self._session:
            await self._session.close()
            self._session = None
        
        self._order_cache.clear()
        
        logger.info("BinanceAccount closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/binance", tags=["Binance"])


async def get_account(
    api_key: str = Query(..., description="Binance API Key"),
    api_secret: str = Query(..., description="Binance API Secret"),
    testnet: bool = Query(True, description="Use testnet")
) -> BinanceAccount:
    """Dependency to get BinanceAccount instance"""
    credentials = BinanceCredentials(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    )
    return BinanceAccount(credentials)


@router.get("/account")
async def get_account_info(
    account: BinanceAccount = Depends(get_account)
):
    """Get Binance account information"""
    return await account.get_account_info()


@router.get("/balance/{asset}")
async def get_balance(
    asset: str,
    account: BinanceAccount = Depends(get_account)
):
    """Get balance for an asset"""
    return await account.get_balance(asset)


@router.get("/balances")
async def get_all_balances(
    account: BinanceAccount = Depends(get_account)
):
    """Get all balances"""
    return await account.get_all_balances()


@router.post("/order")
async def place_order(
    request: BinanceOrderRequest,
    account: BinanceAccount = Depends(get_account)
):
    """Place an order on Binance"""
    return await account.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: int,
    symbol: str = Query(..., description="Symbol"),
    account: BinanceAccount = Depends(get_account)
):
    """Cancel an order"""
    success = await account.cancel_order(order_id, symbol)
    return {"success": success}


@router.get("/order/{order_id}")
async def get_order(
    order_id: int,
    symbol: str = Query(..., description="Symbol"),
    account: BinanceAccount = Depends(get_account)
):
    """Get order details"""
    return await account.get_order(order_id, symbol)


@router.get("/orders/open")
async def get_open_orders(
    symbol: str = Query(..., description="Symbol"),
    account: BinanceAccount = Depends(get_account)
):
    """Get open orders"""
    return await account.get_open_orders(symbol)


@router.get("/positions")
async def get_positions(
    account: BinanceAccount = Depends(get_account)
):
    """Get positions"""
    return await account.get_positions()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BinanceAccount',
    'BinanceAccountType',
    'BinanceOrderStatus',
    'BinanceOrderType',
    'BinanceOrderSide',
    'BinanceTimeInForce',
    'BinanceAccountInfo',
    'BinanceBalance',
    'BinanceOrderRequest',
    'BinanceOrderResponse',
    'BinanceCredentials',
    'BinanceApiResponse',
    'router'
]
