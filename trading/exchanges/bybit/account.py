"""
NEXUS AI TRADING SYSTEM - Bybit Account Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/account.py
Description: Bybit exchange account management with full API integration
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

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BybitAccountType(str, Enum):
    """Bybit account types"""
    SPOT = "spot"
    LINEAR = "linear"  # USDT perpetual
    INVERSE = "inverse"  # Coin-margined
    OPTION = "option"


class BybitOrderStatus(str, Enum):
    """Bybit order status"""
    CREATED = "Created"
    NEW = "New"
    PARTIALLY_FILLED = "PartiallyFilled"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"
    PENDING_CANCEL = "PendingCancel"
    PARTIALLY_FILLED_CANCELLED = "PartiallyFilledCancelled"


class BybitOrderType(str, Enum):
    """Bybit order types"""
    LIMIT = "Limit"
    MARKET = "Market"
    STOP = "Stop"
    STOP_LIMIT = "StopLimit"
    TAKE_PROFIT = "TakeProfit"
    TAKE_PROFIT_LIMIT = "TakeProfitLimit"
    TRAILING_STOP = "TrailingStop"


class BybitOrderSide(str, Enum):
    """Bybit order sides"""
    BUY = "Buy"
    SELL = "Sell"


class BybitTimeInForce(str, Enum):
    """Bybit time in force"""
    GTC = "GTC"  # Good till cancelled
    IOC = "IOC"  # Immediate or cancel
    FOK = "FOK"  # Fill or kill
    POST_ONLY = "PostOnly"


class BybitMarginMode(str, Enum):
    """Bybit margin modes"""
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BybitAccountInfo(BaseModel):
    """Bybit account information"""
    account_id: str
    account_type: BybitAccountType
    balance: Dict[str, float]
    total_equity: float
    available_balance: float
    used_margin: float
    margin_ratio: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class BybitBalance(BaseModel):
    """Bybit balance"""
    coin: str
    equity: float
    available: float
    used_margin: float
    order_margin: float
    position_margin: float
    total: float


class BybitOrderRequest(BaseModel):
    """Bybit order request"""
    symbol: str
    side: BybitOrderSide
    order_type: BybitOrderType = BybitOrderType.LIMIT
    qty: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: BybitTimeInForce = BybitTimeInForce.GTC
    reduce_only: bool = False
    close_on_trigger: bool = False
    position_idx: int = 0
    order_link_id: Optional[str] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    tp_trigger_by: Optional[str] = None
    sl_trigger_by: Optional[str] = None


class BybitOrderResponse(BaseModel):
    """Bybit order response"""
    order_id: str
    order_link_id: str
    symbol: str
    side: BybitOrderSide
    order_type: BybitOrderType
    status: BybitOrderStatus
    price: float
    avg_price: float
    qty: float
    cum_exec_qty: float
    cum_exec_value: float
    time_in_force: BybitTimeInForce
    stop_price: Optional[float] = None
    reduce_only: bool
    close_on_trigger: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BybitCredentials:
    """Bybit API credentials"""
    api_key: str
    api_secret: str
    testnet: bool = True


@dataclass
class BybitApiResponse:
    """Bybit API response"""
    ret_code: int
    ret_msg: str
    result: Dict[str, Any]
    ret_ext_info: Dict[str, Any]
    time: int


# =============================================================================
# BYBIT ACCOUNT
# =============================================================================

class BybitAccount:
    """
    Bybit Exchange Account Management with full API integration.
    
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

    BASE_URL = "https://api.bybit.com"
    TESTNET_BASE_URL = "https://api-testnet.bybit.com"
    
    def __init__(
        self,
        credentials: BybitCredentials,
        account_type: BybitAccountType = BybitAccountType.LINEAR,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize BybitAccount.
        
        Args:
            credentials: Bybit API credentials
            account_type: Bybit account type
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
            'requests_per_second': 50,
            'requests': [],
            'last_reset': datetime.utcnow()
        }
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Order cache
        self._order_cache: Dict[str, Dict[str, Any]] = {}
        
        # Endpoints
        self._endpoints = {
            'spot': '/v5/spot',
            'linear': '/v5/linear',
            'inverse': '/v5/inverse'
        }
        
        self._api_prefix = self._get_api_prefix()
        
        logger.info(f"BybitAccount initialized for {account_type.value}")

    def _get_api_prefix(self) -> str:
        """Get API prefix based on account type"""
        prefixes = {
            BybitAccountType.SPOT: '/v5/spot',
            BybitAccountType.LINEAR: '/v5/linear',
            BybitAccountType.INVERSE: '/v5/inverse',
            BybitAccountType.OPTION: '/v5/option'
        }
        return prefixes.get(self.account_type, '/v5/linear')

    # =========================================================================
    # Session Management
    # =========================================================================

    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession(
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

    @retry_async(max_attempts=3, delay=0.5, backoff=2.0)
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        recv_window: int = 5000
    ) -> BybitApiResponse:
        """
        Make an API request to Bybit.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request data
            signed: Whether request requires signing
            recv_window: Receive window
            
        Returns:
            BybitApiResponse: API response
        """
        try:
            # Check rate limit
            await self._check_rate_limit()
            
            # Prepare request
            url = f"{self.base_url}{self._api_prefix}{endpoint}"
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Add authentication if required
            if signed:
                timestamp = str(int(time.time() * 1000))
                headers['X-BAPI-API-KEY'] = self.credentials.api_key
                headers['X-BAPI-TIMESTAMP'] = timestamp
                headers['X-BAPI-RECV-WINDOW'] = str(recv_window)
                
                # Build query string
                query_string = ''
                if method == 'GET' and params:
                    query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                elif method == 'POST' and data:
                    query_string = json.dumps(data, separators=(',', ':'))
                
                # Generate signature
                signature_payload = timestamp + self.credentials.api_key + recv_window + query_string
                signature = hmac.new(
                    self.credentials.api_secret.encode('utf-8'),
                    signature_payload.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                headers['X-BAPI-SIGN'] = signature
            
            # Make request
            async with self._session.request(
                method=method,
                url=url,
                params=params if method == 'GET' else None,
                json=data if method == 'POST' else None,
                headers=headers
            ) as response:
                # Update rate limit
                self._update_rate_limit()
                
                # Parse response
                response_data = await response.json()
                
                # Check for error
                if response_data.get('retCode') != 0:
                    return BybitApiResponse(
                        ret_code=response_data.get('retCode', -1),
                        ret_msg=response_data.get('retMsg', 'Unknown error'),
                        result={},
                        ret_ext_info=response_data.get('retExtInfo', {}),
                        time=response_data.get('time', 0)
                    )
                
                return BybitApiResponse(
                    ret_code=response_data.get('retCode', 0),
                    ret_msg=response_data.get('retMsg', 'Success'),
                    result=response_data.get('result', {}),
                    ret_ext_info=response_data.get('retExtInfo', {}),
                    time=response_data.get('time', 0)
                )
                
        except asyncio.TimeoutError:
            return BybitApiResponse(
                ret_code=10001,
                ret_msg="Request timeout",
                result={},
                ret_ext_info={},
                time=int(time.time() * 1000)
            )
        except Exception as e:
            logger.error(f"API request error: {e}")
            return BybitApiResponse(
                ret_code=10002,
                ret_msg=str(e),
                result={},
                ret_ext_info={},
                time=int(time.time() * 1000)
            )

    async def _check_rate_limit(self) -> None:
        """Check if rate limit is exceeded"""
        now = datetime.utcnow()
        
        # Reset rate limit if second has passed
        if (now - self._rate_limit['last_reset']).seconds >= 1:
            self._rate_limit['requests'] = []
            self._rate_limit['last_reset'] = now
        
        # Check if limit exceeded
        if len(self._rate_limit['requests']) >= self._rate_limit['requests_per_second']:
            await asyncio.sleep(0.05)
            await self._check_rate_limit()

    def _update_rate_limit(self) -> None:
        """Update rate limit tracking"""
        self._rate_limit['requests'].append(datetime.utcnow())

    # =========================================================================
    # Account Information
    # =========================================================================

    async def get_account_info(self) -> BybitAccountInfo:
        """
        Get account information.
        
        Returns:
            BybitAccountInfo: Account information
        """
        try:
            endpoint = '/account/info' if self.account_type == BybitAccountType.SPOT else '/account/info'
            
            response = await self._request(
                method='GET',
                endpoint=endpoint,
                signed=True
            )
            
            if response.ret_code != 0:
                raise Exception(response.ret_msg)
            
            data = response.result
            
            # Parse balances
            balances = {}
            total_equity = 0
            available_balance = 0
            
            if self.account_type == BybitAccountType.SPOT:
                for balance in data.get('balances', []):
                    coin = balance['coin']
                    free = float(balance['free'])
                    locked = float(balance['locked'])
                    total = free + locked
                    
                    if total > 0:
                        balances[coin] = {
                            'free': free,
                            'locked': locked,
                            'total': total
                        }
                        
                        # Get price for USD value
                        price = await self._get_price(coin)
                        if price:
                            total_equity += total * price
                            available_balance += free * price
            else:
                for balance in data.get('balance', []):
                    coin = balance['coin']
                    equity = float(balance['equity'])
                    available = float(balance['available'])
                    
                    if equity > 0:
                        balances[coin] = {
                            'free': available,
                            'locked': equity - available,
                            'total': equity
                        }
                        
                        total_equity += equity
                        available_balance += available
            
            return BybitAccountInfo(
                account_id=data.get('accountId', ''),
                account_type=self.account_type,
                balance=balances,
                total_equity=total_equity,
                available_balance=available_balance,
                used_margin=0,
                margin_ratio=0,
                positions=[],
                orders=[],
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            raise

    async def _get_price(self, coin: str) -> Optional[float]:
        """Get price of coin in USD"""
        try:
            if coin == 'USDT':
                return 1.0
            
            symbol = f"{coin}USDT"
            response = await self._request(
                method='GET',
                endpoint='/tickers',
                params={'symbol': symbol}
            )
            
            if response.ret_code == 0 and response.result:
                tickers = response.result.get('list', [])
                if tickers:
                    return float(tickers[0].get('lastPrice', 0))
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting price for {coin}: {e}")
            return None

    # =========================================================================
    # Balance Management
    # =========================================================================

    async def get_balance(self, coin: str) -> Optional[BybitBalance]:
        """
        Get balance for a coin.
        
        Args:
            coin: Coin symbol
            
        Returns:
            Optional[BybitBalance]: Balance
        """
        try:
            account = await self.get_account_info()
            
            if coin in account.balance:
                balance = account.balance[coin]
                return BybitBalance(
                    coin=coin,
                    equity=balance['total'],
                    available=balance['free'],
                    used_margin=0,
                    order_margin=0,
                    position_margin=0,
                    total=balance['total']
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting balance for {coin}: {e}")
            return None

    async def get_all_balances(self) -> Dict[str, BybitBalance]:
        """
        Get all balances.
        
        Returns:
            Dict[str, BybitBalance]: All balances
        """
        try:
            account = await self.get_account_info()
            balances = {}
            
            for coin, balance in account.balance.items():
                balances[coin] = BybitBalance(
                    coin=coin,
                    equity=balance['total'],
                    available=balance['free'],
                    used_margin=0,
                    order_margin=0,
                    position_margin=0,
                    total=balance['total']
                )
            
            return balances
            
        except Exception as e:
            logger.error(f"Error getting all balances: {e}")
            return {}

    # =========================================================================
    # Order Management
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
            endpoint = '/order/create' if self.account_type == BybitAccountType.SPOT else '/order/create'
            
            response = await self._request(
                method='POST',
                endpoint=endpoint,
                data=data,
                signed=True
            )
            
            if response.ret_code != 0:
                raise Exception(response.ret_msg)
            
            result = response.result
            
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
            self._order_cache[order_response.order_id] = order_response.dict()
            
            logger.info(f"Order placed: {order_response.order_id} for {request.symbol}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
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
            data = {
                'symbol': symbol,
                'orderId': order_id
            }
            
            response = await self._request(
                method='POST',
                endpoint='/order/cancel',
                data=data,
                signed=True
            )
            
            if response.ret_code != 0:
                raise Exception(response.ret_msg)
            
            # Remove from cache
            if order_id in self._order_cache:
                del self._order_cache[order_id]
            
            logger.info(f"Order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

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
                cached = self._order_cache[order_id]
                return BybitOrderResponse(**cached)
            
            params = {
                'symbol': symbol,
                'orderId': order_id
            }
            
            response = await self._request(
                method='GET',
                endpoint='/order',
                params=params,
                signed=True
            )
            
            if response.ret_code != 0:
                raise Exception(response.ret_msg)
            
            result = response.result
            
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
            self._order_cache[order_response.order_id] = order_response.dict()
            
            return order_response
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Bybit account connection"""
        if self._session:
            await self._session.close()
            self._session = None
        
        self._order_cache.clear()
        
        logger.info("BybitAccount closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/bybit", tags=["Bybit"])


async def get_account(
    api_key: str = Query(..., description="Bybit API Key"),
    api_secret: str = Query(..., description="Bybit API Secret"),
    testnet: bool = Query(True, description="Use testnet"),
    account_type: BybitAccountType = Query(BybitAccountType.LINEAR)
) -> BybitAccount:
    """Dependency to get BybitAccount instance"""
    credentials = BybitCredentials(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    )
    return BybitAccount(credentials, account_type)


@router.get("/account")
async def get_account_info(
    account: BybitAccount = Depends(get_account)
):
    """Get Bybit account information"""
    return await account.get_account_info()


@router.get("/balance/{coin}")
async def get_balance(
    coin: str,
    account: BybitAccount = Depends(get_account)
):
    """Get balance for a coin"""
    return await account.get_balance(coin)


@router.get("/balances")
async def get_all_balances(
    account: BybitAccount = Depends(get_account)
):
    """Get all balances"""
    return await account.get_all_balances()


@router.post("/order")
async def place_order(
    request: BybitOrderRequest,
    account: BybitAccount = Depends(get_account)
):
    """Place an order on Bybit"""
    return await account.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    symbol: str = Query(..., description="Symbol"),
    account: BybitAccount = Depends(get_account)
):
    """Cancel an order"""
    success = await account.cancel_order(order_id, symbol)
    return {"success": success}


@router.get("/order/{order_id}")
async def get_order(
    order_id: str,
    symbol: str = Query(..., description="Symbol"),
    account: BybitAccount = Depends(get_account)
):
    """Get order details"""
    return await account.get_order(order_id, symbol)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitAccount',
    'BybitAccountType',
    'BybitOrderStatus',
    'BybitOrderType',
    'BybitOrderSide',
    'BybitTimeInForce',
    'BybitMarginMode',
    'BybitAccountInfo',
    'BybitBalance',
    'BybitOrderRequest',
    'BybitOrderResponse',
    'BybitCredentials',
    'BybitApiResponse',
    'router'
]
