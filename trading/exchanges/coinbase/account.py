"""
NEXUS AI TRADING SYSTEM - Coinbase Account Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/coinbase/account.py
Description: Coinbase exchange account management with full API integration
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

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class CoinbaseAccountType(str, Enum):
    """Coinbase account types"""
    SPOT = "spot"
    MARGIN = "margin"
    STAKING = "staking"


class CoinbaseOrderStatus(str, Enum):
    """Coinbase order status"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"


class CoinbaseOrderType(str, Enum):
    """Coinbase order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class CoinbaseOrderSide(str, Enum):
    """Coinbase order sides"""
    BUY = "buy"
    SELL = "sell"


class CoinbaseTimeInForce(str, Enum):
    """Coinbase time in force"""
    GTC = "GTC"  # Good till cancelled
    IOC = "IOC"  # Immediate or cancel
    FOK = "FOK"  # Fill or kill
    GTD = "GTD"  # Good till date


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CoinbaseAccountInfo(BaseModel):
    """Coinbase account information"""
    account_id: str
    account_type: CoinbaseAccountType
    balances: Dict[str, float]
    total_balance_usd: float
    available_balance_usd: float
    holdings: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    timestamp: datetime


class CoinbaseBalance(BaseModel):
    """Coinbase balance"""
    currency: str
    amount: float
    available: float
    hold: float


class CoinbaseOrderRequest(BaseModel):
    """Coinbase order request"""
    product_id: str
    side: CoinbaseOrderSide
    order_type: CoinbaseOrderType = CoinbaseOrderType.LIMIT
    size: Optional[float] = None
    funds: Optional[float] = None
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: CoinbaseTimeInForce = CoinbaseTimeInForce.GTC
    end_time: Optional[datetime] = None
    post_only: bool = False
    client_order_id: Optional[str] = None


class CoinbaseOrderResponse(BaseModel):
    """Coinbase order response"""
    order_id: str
    client_order_id: str
    product_id: str
    side: CoinbaseOrderSide
    order_type: CoinbaseOrderType
    status: CoinbaseOrderStatus
    price: float
    filled_size: float
    size: float
    funds: float
    filled_funds: float
    time_in_force: CoinbaseTimeInForce
    stop_price: Optional[float] = None
    post_only: bool
    created_at: datetime
    done_at: Optional[datetime] = None
    done_reason: Optional[str] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CoinbaseCredentials:
    """Coinbase API credentials"""
    api_key: str
    api_secret: str
    passphrase: str
    use_sandbox: bool = True


@dataclass
class CoinbaseApiResponse:
    """Coinbase API response"""
    status: int
    data: Dict[str, Any]
    error: Optional[str] = None


# =============================================================================
# COINBASE ACCOUNT
# =============================================================================

class CoinbaseAccount:
    """
    Coinbase Exchange Account Management with full API integration.
    
    Features:
    - Account information
    - Balance management
    - Order placement and management
    - Position management
    - API authentication
    - Rate limiting
    - Error handling
    - Sandbox support
    """

    BASE_URL = "https://api.coinbase.com"
    SANDBOX_BASE_URL = "https://api-public.sandbox.exchange.coinbase.com"
    
    def __init__(
        self,
        credentials: CoinbaseCredentials,
        account_type: CoinbaseAccountType = CoinbaseAccountType.SPOT,
        config: Optional[ExchangeConfig] = None
    ):
        """
        Initialize CoinbaseAccount.
        
        Args:
            credentials: Coinbase API credentials
            account_type: Coinbase account type
            config: Exchange configuration
        """
        self.credentials = credentials
        self.account_type = account_type
        self.config = config or ExchangeConfig()
        
        # Base URL
        self.base_url = self.SANDBOX_BASE_URL if credentials.use_sandbox else self.BASE_URL
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting
        self._rate_limit: Dict[str, Any] = {
            'requests_per_second': 10,
            'requests': [],
            'last_reset': datetime.utcnow()
        }
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Order cache
        self._order_cache: Dict[str, Dict[str, Any]] = {}
        
        # Product cache
        self._product_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"CoinbaseAccount initialized for {account_type.value}")

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
        signed: bool = False
    ) -> CoinbaseApiResponse:
        """
        Make an API request to Coinbase.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request data
            signed: Whether request requires signing
            
        Returns:
            CoinbaseApiResponse: API response
        """
        try:
            # Check rate limit
            await self._check_rate_limit()
            
            # Prepare request
            url = f"{self.base_url}{endpoint}"
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Add authentication if required
            if signed:
                timestamp = str(int(time.time()))
                method_str = method
                path = endpoint
                
                # Build message
                if method == 'GET':
                    if params:
                        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                        path = f"{endpoint}?{query_string}"
                    message = f"{timestamp}{method_str}{path}"
                else:
                    if data:
                        body = json.dumps(data, separators=(',', ':'))
                        message = f"{timestamp}{method_str}{path}{body}"
                    else:
                        message = f"{timestamp}{method_str}{path}"
                
                # Generate signature
                signature = hmac.new(
                    self.credentials.api_secret.encode('utf-8'),
                    message.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                headers['CB-ACCESS-KEY'] = self.credentials.api_key
                headers['CB-ACCESS-SIGN'] = signature
                headers['CB-ACCESS-TIMESTAMP'] = timestamp
                headers['CB-ACCESS-PASSPHRASE'] = self.credentials.passphrase
            
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
                
                if response.status >= 400:
                    error_msg = response_data.get('message', 'Unknown error')
                    return CoinbaseApiResponse(
                        status=response.status,
                        data={},
                        error=error_msg
                    )
                
                return CoinbaseApiResponse(
                    status=response.status,
                    data=response_data
                )
                
        except asyncio.TimeoutError:
            return CoinbaseApiResponse(
                status=408,
                data={},
                error="Request timeout"
            )
        except Exception as e:
            logger.error(f"API request error: {e}")
            return CoinbaseApiResponse(
                status=500,
                data={},
                error=str(e)
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
            await asyncio.sleep(0.1)
            await self._check_rate_limit()

    def _update_rate_limit(self) -> None:
        """Update rate limit tracking"""
        self._rate_limit['requests'].append(datetime.utcnow())

    # =========================================================================
    # Account Information
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def get_account_info(self) -> CoinbaseAccountInfo:
        """
        Get account information.
        
        Returns:
            CoinbaseAccountInfo: Account information
        """
        try:
            # Get balances
            balances_response = await self._request(
                method='GET',
                endpoint='/api/v3/brokerage/accounts',
                signed=True
            )
            
            if balances_response.error:
                raise Exception(balances_response.error)
            
            data = balances_response.data
            
            balances = {}
            total_balance = 0
            available_balance = 0
            
            for account in data.get('accounts', []):
                currency = account.get('currency')
                balance = float(account.get('balance', 0))
                available = float(account.get('available_balance', {}).get('value', 0))
                hold = float(account.get('hold', {}).get('value', 0))
                
                if balance > 0:
                    balances[currency] = {
                        'total': balance,
                        'available': available,
                        'hold': hold
                    }
                    
                    # Get price for USD value
                    price = await self._get_price(currency)
                    if price:
                        total_balance += balance * price
                        available_balance += available * price
            
            return CoinbaseAccountInfo(
                account_id=data.get('id', ''),
                account_type=self.account_type,
                balances=balances,
                total_balance_usd=total_balance,
                available_balance_usd=available_balance,
                holdings=[],
                orders=[],
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            raise

    async def _get_price(self, currency: str) -> Optional[float]:
        """Get price of currency in USD"""
        try:
            if currency == 'USD':
                return 1.0
            
            product_id = f"{currency}-USD"
            response = await self._request(
                method='GET',
                endpoint=f'/api/v3/brokerage/products/{product_id}/ticker',
                signed=True
            )
            
            if response.data:
                return float(response.data.get('price', 0))
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting price for {currency}: {e}")
            return None

    # =========================================================================
    # Balance Management
    # =========================================================================

    async def get_balance(self, currency: str) -> Optional[CoinbaseBalance]:
        """
        Get balance for a currency.
        
        Args:
            currency: Currency symbol
            
        Returns:
            Optional[CoinbaseBalance]: Balance
        """
        try:
            account = await self.get_account_info()
            
            if currency in account.balances:
                balance = account.balances[currency]
                return CoinbaseBalance(
                    currency=currency,
                    amount=balance['total'],
                    available=balance['available'],
                    hold=balance['hold']
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting balance for {currency}: {e}")
            return None

    async def get_all_balances(self) -> Dict[str, CoinbaseBalance]:
        """
        Get all balances.
        
        Returns:
            Dict[str, CoinbaseBalance]: All balances
        """
        try:
            account = await self.get_account_info()
            balances = {}
            
            for currency, balance in account.balances.items():
                balances[currency] = CoinbaseBalance(
                    currency=currency,
                    amount=balance['total'],
                    available=balance['available'],
                    hold=balance['hold']
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
        request: CoinbaseOrderRequest
    ) -> CoinbaseOrderResponse:
        """
        Place an order on Coinbase.
        
        Args:
            request: Order request
            
        Returns:
            CoinbaseOrderResponse: Order response
        """
        try:
            # Prepare order data
            data = {
                'product_id': request.product_id,
                'side': request.side.value,
                'type': request.order_type.value,
                'time_in_force': request.time_in_force.value,
                'post_only': request.post_only
            }
            
            if request.size:
                data['size'] = str(request.size)
            
            if request.funds:
                data['funds'] = str(request.funds)
            
            if request.price:
                data['price'] = str(request.price)
            
            if request.stop_price:
                data['stop_price'] = str(request.stop_price)
            
            if request.client_order_id:
                data['client_order_id'] = request.client_order_id
            
            if request.end_time:
                data['end_time'] = request.end_time.isoformat()
            
            # Place order
            response = await self._request(
                method='POST',
                endpoint='/api/v3/brokerage/orders',
                data=data,
                signed=True
            )
            
            if response.error:
                raise Exception(response.error)
            
            result = response.data
            
            # Parse response
            order_response = CoinbaseOrderResponse(
                order_id=result.get('order_id'),
                client_order_id=result.get('client_order_id'),
                product_id=result.get('product_id'),
                side=CoinbaseOrderSide(result.get('side')),
                order_type=CoinbaseOrderType(result.get('type')),
                status=CoinbaseOrderStatus(result.get('status')),
                price=float(result.get('price', 0)),
                filled_size=float(result.get('filled_size', 0)),
                size=float(result.get('size', 0)),
                funds=float(result.get('funds', 0)),
                filled_funds=float(result.get('filled_funds', 0)),
                time_in_force=CoinbaseTimeInForce(result.get('time_in_force', 'GTC')),
                stop_price=float(result.get('stop_price')) if result.get('stop_price') else None,
                post_only=result.get('post_only', False),
                created_at=datetime.utcnow(),
                done_at=None,
                done_reason=None
            )
            
            # Cache order
            self._order_cache[order_response.order_id] = order_response.dict()
            
            logger.info(f"Order placed: {order_response.order_id} for {request.product_id}")
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
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
            response = await self._request(
                method='POST',
                endpoint=f'/api/v3/brokerage/orders/{order_id}/cancel',
                signed=True
            )
            
            if response.error:
                raise Exception(response.error)
            
            # Remove from cache
            if order_id in self._order_cache:
                del self._order_cache[order_id]
            
            logger.info(f"Order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    @retry_async(max_attempts=3, delay=0.5)
    async def get_order(self, order_id: str) -> Optional[CoinbaseOrderResponse]:
        """
        Get order details.
        
        Args:
            order_id: Order ID
            
        Returns:
            Optional[CoinbaseOrderResponse]: Order details
        """
        try:
            # Check cache
            if order_id in self._order_cache:
                cached = self._order_cache[order_id]
                return CoinbaseOrderResponse(**cached)
            
            response = await self._request(
                method='GET',
                endpoint=f'/api/v3/brokerage/orders/{order_id}',
                signed=True
            )
            
            if response.error:
                raise Exception(response.error)
            
            result = response.data
            
            order_response = CoinbaseOrderResponse(
                order_id=result.get('order_id'),
                client_order_id=result.get('client_order_id'),
                product_id=result.get('product_id'),
                side=CoinbaseOrderSide(result.get('side')),
                order_type=CoinbaseOrderType(result.get('type')),
                status=CoinbaseOrderStatus(result.get('status')),
                price=float(result.get('price', 0)),
                filled_size=float(result.get('filled_size', 0)),
                size=float(result.get('size', 0)),
                funds=float(result.get('funds', 0)),
                filled_funds=float(result.get('filled_funds', 0)),
                time_in_force=CoinbaseTimeInForce(result.get('time_in_force', 'GTC')),
                stop_price=float(result.get('stop_price')) if result.get('stop_price') else None,
                post_only=result.get('post_only', False),
                created_at=datetime.utcnow(),
                done_at=None,
                done_reason=None
            )
            
            # Cache order
            self._order_cache[order_response.order_id] = order_response.dict()
            
            return order_response
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    @retry_async(max_attempts=3, delay=0.5)
    async def get_open_orders(self, product_id: Optional[str] = None) -> List[CoinbaseOrderResponse]:
        """
        Get open orders.
        
        Args:
            product_id: Product ID (optional)
            
        Returns:
            List[CoinbaseOrderResponse]: Open orders
        """
        try:
            params = {}
            if product_id:
                params['product_id'] = product_id
            
            response = await self._request(
                method='GET',
                endpoint='/api/v3/brokerage/orders/open',
                params=params,
                signed=True
            )
            
            if response.error:
                raise Exception(response.error)
            
            orders = []
            for data in response.data.get('orders', []):
                orders.append(CoinbaseOrderResponse(
                    order_id=data.get('order_id'),
                    client_order_id=data.get('client_order_id'),
                    product_id=data.get('product_id'),
                    side=CoinbaseOrderSide(data.get('side')),
                    order_type=CoinbaseOrderType(data.get('type')),
                    status=CoinbaseOrderStatus(data.get('status')),
                    price=float(data.get('price', 0)),
                    filled_size=float(data.get('filled_size', 0)),
                    size=float(data.get('size', 0)),
                    funds=float(data.get('funds', 0)),
                    filled_funds=float(data.get('filled_funds', 0)),
                    time_in_force=CoinbaseTimeInForce(data.get('time_in_force', 'GTC')),
                    stop_price=float(data.get('stop_price')) if data.get('stop_price') else None,
                    post_only=data.get('post_only', False),
                    created_at=datetime.utcnow(),
                    done_at=None,
                    done_reason=None
                ))
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []

    # =========================================================================
    # Product Information
    # =========================================================================

    async def get_products(self) -> List[Dict[str, Any]]:
        """
        Get all products.
        
        Returns:
            List[Dict[str, Any]]: Products
        """
        try:
            response = await self._request(
                method='GET',
                endpoint='/api/v3/brokerage/products'
            )
            
            if response.error:
                raise Exception(response.error)
            
            return response.data.get('products', [])
            
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return []

    async def get_product(self, product_id: str) -> Dict[str, Any]:
        """
        Get product details.
        
        Args:
            product_id: Product ID
            
        Returns:
            Dict[str, Any]: Product details
        """
        try:
            # Check cache
            if product_id in self._product_cache:
                return self._product_cache[product_id]
            
            response = await self._request(
                method='GET',
                endpoint=f'/api/v3/brokerage/products/{product_id}'
            )
            
            if response.error:
                raise Exception(response.error)
            
            self._product_cache[product_id] = response.data
            
            return response.data
            
        except Exception as e:
            logger.error(f"Error getting product {product_id}: {e}")
            return {}

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the Coinbase account connection"""
        if self._session:
            await self._session.close()
            self._session = None
        
        self._order_cache.clear()
        self._product_cache.clear()
        
        logger.info("CoinbaseAccount closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/coinbase", tags=["Coinbase"])


async def get_account(
    api_key: str = Query(..., description="Coinbase API Key"),
    api_secret: str = Query(..., description="Coinbase API Secret"),
    passphrase: str = Query(..., description="Coinbase Passphrase"),
    use_sandbox: bool = Query(True, description="Use sandbox")
) -> CoinbaseAccount:
    """Dependency to get CoinbaseAccount instance"""
    credentials = CoinbaseCredentials(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        use_sandbox=use_sandbox
    )
    return CoinbaseAccount(credentials)


@router.get("/account")
async def get_account_info(
    account: CoinbaseAccount = Depends(get_account)
):
    """Get Coinbase account information"""
    return await account.get_account_info()


@router.get("/balance/{currency}")
async def get_balance(
    currency: str,
    account: CoinbaseAccount = Depends(get_account)
):
    """Get balance for a currency"""
    return await account.get_balance(currency)


@router.get("/balances")
async def get_all_balances(
    account: CoinbaseAccount = Depends(get_account)
):
    """Get all balances"""
    return await account.get_all_balances()


@router.post("/order")
async def place_order(
    request: CoinbaseOrderRequest,
    account: CoinbaseAccount = Depends(get_account)
):
    """Place an order on Coinbase"""
    return await account.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    account: CoinbaseAccount = Depends(get_account)
):
    """Cancel an order"""
    success = await account.cancel_order(order_id)
    return {"success": success}


@router.get("/order/{order_id}")
async def get_order(
    order_id: str,
    account: CoinbaseAccount = Depends(get_account)
):
    """Get order details"""
    return await account.get_order(order_id)


@router.get("/orders/open")
async def get_open_orders(
    product_id: Optional[str] = Query(None),
    account: CoinbaseAccount = Depends(get_account)
):
    """Get open orders"""
    return await account.get_open_orders(product_id)


@router.get("/products")
async def get_products(
    account: CoinbaseAccount = Depends(get_account)
):
    """Get all products"""
    return await account.get_products()


@router.get("/product/{product_id}")
async def get_product(
    product_id: str,
    account: CoinbaseAccount = Depends(get_account)
):
    """Get product details"""
    return await account.get_product(product_id)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CoinbaseAccount',
    'CoinbaseAccountType',
    'CoinbaseOrderStatus',
    'CoinbaseOrderType',
    'CoinbaseOrderSide',
    'CoinbaseTimeInForce',
    'CoinbaseAccountInfo',
    'CoinbaseBalance',
    'CoinbaseOrderRequest',
    'CoinbaseOrderResponse',
    'CoinbaseCredentials',
    'CoinbaseApiResponse',
    'router'
]
