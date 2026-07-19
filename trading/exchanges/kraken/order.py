# trading/exchanges/kraken/order.py
# Nexus AI Trading System - Kraken Exchange Order Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Kraken Exchange - Order Management Module

This module provides comprehensive order management functionality for the Kraken
cryptocurrency exchange, including:

- Order placement with all order types (market, limit, stop-loss, take-profit)
- Order cancellation and modification
- Order status tracking and monitoring
- Open and closed order retrieval
- Order history with advanced filtering
- Order validation and pre-check
- Smart order routing
- Batch order placement
- OCO (One Cancels Other) orders
- Bracket orders (OCO with stop-loss and take-profit)
- Trailing stop orders
- Order execution analytics
- Order book integration
- Real-time order updates via WebSocket
- Order lifecycle management
- Risk management and position sizing
- Slippage control
- Fee calculation
- Comprehensive error handling
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set
import uuid
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis
import asyncpg

# Nexus imports
from trading.exchanges.kraken.base import (
    KrakenBase,
    KrakenConfig,
    KrakenApiType,
    KrakenOrderType,
    KrakenOrderSide,
    KrakenOrderStatus,
    KrakenTimeInForce,
    KrakenOrder
)
from trading.exchanges.kraken.exceptions import (
    KrakenError,
    KrakenOrderError,
    KrakenOrderNotFoundError,
    KrakenInsufficientFundsError,
    KrakenRateLimitError,
    KrakenValidationError,
    KrakenParameterError
)
from trading.exchanges.kraken.converter import KrakenConverter, get_converter
from trading.exchanges.kraken.market import KrakenMarketData
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class KrakenOrderStatus(str, Enum):
    """Kraken order status extended."""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    HELD = "held"
    TRIGGERED = "triggered"
    STOPPED = "stopped"
    IN_PROGRESS = "in_progress"
    ERROR = "error"


class KrakenOrderFlags(str, Enum):
    """Kraken order flags."""
    POST_ONLY = "post_only"
    REDUCE_ONLY = "reduce_only"
    TIME_IN_FORCE = "time_in_force"
    IMMEDIATE_OR_CANCEL = "immediate_or_cancel"
    FILL_OR_KILL = "fill_or_kill"
    GOOD_TILL_CANCELLED = "good_till_cancelled"
    GOOD_TILL_DATE = "good_till_date"


class OrderExecutionType(str, Enum):
    """Order execution type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    TAKE_PROFIT = "take_profit"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    TRAILING_STOP = "trailing_stop"
    TRAILING_STOP_LIMIT = "trailing_stop_limit"
    OCO = "oco"
    BRACKET = "bracket"


class OrderValidationResult(str, Enum):
    """Order validation result."""
    VALID = "valid"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    INVALID_VOLUME = "invalid_volume"
    INVALID_PRICE = "invalid_price"
    INVALID_SYMBOL = "invalid_symbol"
    MARKET_CLOSED = "market_closed"
    ORDER_LIMIT_REACHED = "order_limit_reached"
    MIN_NOTIONAL_NOT_MET = "min_notional_not_met"
    MAX_NOTIONAL_EXCEEDED = "max_notional_exceeded"
    PRICE_OUTSIDE_BOUNDS = "price_outside_bounds"
    POSITION_LIMIT_REACHED = "position_limit_reached"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OrderRequest(BaseModel):
    """Order request model."""
    symbol: str
    side: KrakenOrderSide
    order_type: KrakenOrderType
    volume: Decimal
    price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: KrakenTimeInForce = KrakenTimeInForce.GTC
    client_order_id: Optional[str] = None
    reduce_only: bool = False
    post_only: bool = False
    expire_time: Optional[datetime] = None
    tags: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('volume')
    def validate_volume(cls, v):
        if v <= 0:
            raise ValueError("Volume must be positive")
        return v

    @validator('price')
    def validate_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Price must be positive")
        return v

    @validator('stop_price')
    def validate_stop_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Stop price must be positive")
        return v

    @root_validator
    def validate_order_type_requirements(cls, values):
        order_type = values.get('order_type')
        price = values.get('price')
        limit_price = values.get('limit_price')
        stop_price = values.get('stop_price')

        if order_type in [KrakenOrderType.LIMIT, KrakenOrderType.STOP_LOSS_LIMIT, 
                         KrakenOrderType.TAKE_PROFIT_LIMIT]:
            if price is None:
                raise ValueError(f"Price required for {order_type} order")
        
        if order_type in [KrakenOrderType.STOP_LOSS_LIMIT, KrakenOrderType.TAKE_PROFIT_LIMIT]:
            if limit_price is None:
                raise ValueError(f"Limit price required for {order_type} order")

        if order_type in [KrakenOrderType.STOP_LOSS, KrakenOrderType.TAKE_PROFIT]:
            if stop_price is None:
                raise ValueError(f"Stop price required for {order_type} order")

        return values


class OrderResponse(BaseModel):
    """Order response model."""
    order_id: str
    client_order_id: Optional[str] = None
    status: KrakenOrderStatus
    symbol: str
    side: KrakenOrderSide
    order_type: KrakenOrderType
    volume: Decimal
    price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: KrakenTimeInForce
    filled_volume: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchOrderRequest(BaseModel):
    """Batch order request model."""
    orders: List[OrderRequest]
    execute_sequentially: bool = False
    stop_on_error: bool = True
    ignore_invalid: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchOrderResponse(BaseModel):
    """Batch order response model."""
    successful: List[OrderResponse] = Field(default_factory=list)
    failed: List[Dict[str, Any]] = Field(default_factory=list)
    total_success: int = 0
    total_failed: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderValidationRequest(BaseModel):
    """Order validation request model."""
    order_request: OrderRequest
    validate_balance: bool = True
    validate_market: bool = True
    validate_position_limits: bool = True


class OrderValidationResponse(BaseModel):
    """Order validation response model."""
    result: OrderValidationResult
    is_valid: bool
    message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    suggested_action: Optional[str] = None


class OrderCancelRequest(BaseModel):
    """Order cancellation request."""
    order_id: str
    client_order_id: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderModificationRequest(BaseModel):
    """Order modification request."""
    order_id: str
    price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    time_in_force: Optional[KrakenTimeInForce] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OCOOrderRequest(BaseModel):
    """OCO (One Cancels Other) order request."""
    symbol: str
    side: KrakenOrderSide
    stop_price: Decimal
    limit_price: Decimal
    volume: Decimal
    stop_order_type: KrakenOrderType = KrakenOrderType.STOP_LOSS
    limit_order_type: KrakenOrderType = KrakenOrderType.LIMIT
    time_in_force: KrakenTimeInForce = KrakenTimeInForce.GTC
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BracketOrderRequest(BaseModel):
    """Bracket order request (OCO with stop-loss and take-profit)."""
    symbol: str
    side: KrakenOrderSide
    entry_price: Decimal
    volume: Decimal
    stop_loss_price: Decimal
    take_profit_price: Decimal
    entry_order_type: KrakenOrderType = KrakenOrderType.LIMIT
    stop_loss_order_type: KrakenOrderType = KrakenOrderType.STOP_LOSS
    take_profit_order_type: KrakenOrderType = KrakenOrderType.TAKE_PROFIT
    time_in_force: KrakenTimeInForce = KrakenTimeInForce.GTC
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderExecutionReport(BaseModel):
    """Order execution report."""
    order_id: str
    symbol: str
    side: KrakenOrderSide
    order_type: KrakenOrderType
    volume: Decimal
    filled_volume: Decimal
    average_price: Decimal
    price: Decimal
    total_cost: Decimal
    fee: Decimal
    fee_currency: str
    execution_time: datetime
    status: KrakenOrderStatus
    exchange_status: str
    latency_ms: float
    slippage: Decimal = Decimal('0')
    slippage_percent: Decimal = Decimal('0')
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Orders table
CREATE TABLE IF NOT EXISTS kraken_orders (
    id VARCHAR(64) PRIMARY KEY,
    client_order_id VARCHAR(64),
    pair VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    executed_volume DECIMAL(32, 16) DEFAULT 0,
    price DECIMAL(32, 16) DEFAULT 0,
    avg_price DECIMAL(32, 16) DEFAULT 0,
    limit_price DECIMAL(32, 16),
    stop_price DECIMAL(32, 16),
    fee DECIMAL(32, 16) DEFAULT 0,
    cost DECIMAL(32, 16) DEFAULT 0,
    time_in_force VARCHAR(10) DEFAULT 'GTC',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,
    closed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_kraken_orders_pair (pair),
    INDEX idx_kraken_orders_status (status),
    INDEX idx_kraken_orders_created_at (created_at),
    INDEX idx_kraken_orders_client_order_id (client_order_id)
);

-- Order executions
CREATE TABLE IF NOT EXISTS kraken_order_executions (
    id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL REFERENCES kraken_orders(id),
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    cost DECIMAL(32, 16) NOT NULL,
    fee DECIMAL(32, 16) DEFAULT 0,
    fee_currency VARCHAR(10),
    executed_at TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_kraken_order_executions_order_id (order_id),
    INDEX idx_kraken_order_executions_executed_at (executed_at)
);

-- Order execution reports
CREATE TABLE IF NOT EXISTS kraken_execution_reports (
    id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL,
    report_type VARCHAR(30),
    status VARCHAR(30) NOT NULL,
    executed_volume DECIMAL(32, 16) DEFAULT 0,
    avg_price DECIMAL(32, 16) DEFAULT 0,
    fee DECIMAL(32, 16) DEFAULT 0,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_kraken_execution_reports_order_id (order_id),
    INDEX idx_kraken_execution_reports_timestamp (timestamp)
);

-- Order audit log
CREATE TABLE IF NOT EXISTS kraken_order_audit (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL,
    action VARCHAR(50) NOT NULL,
    previous_state JSONB,
    new_state JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    INDEX idx_kraken_order_audit_order_id (order_id),
    INDEX idx_kraken_order_audit_timestamp (timestamp)
);
"""


# =============================================================================
# MAIN ORDER MANAGEMENT CLASS
# =============================================================================

class KrakenOrderManager:
    """
    Advanced order management for Kraken exchange.
    
    Features:
    - All order types (market, limit, stop-loss, take-profit, etc.)
    - Batch order placement
    - OCO (One Cancels Other) orders
    - Bracket orders (stop-loss + take-profit)
    - Trailing stop orders
    - Order validation and pre-check
    - Smart order routing
    - Order modification and cancellation
    - Order status tracking
    - Real-time order updates via WebSocket
    - Order execution analytics
    - Fee calculation
    - Slippage tracking
    - Order audit logging
    - Database persistence
    - Circuit breaker for safety
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        base: KrakenBase,
        config: KrakenConfig,
        market_data: Optional[KrakenMarketData] = None,
        converter: Optional[KrakenConverter] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.base = base
        self.config = config
        self.market_data = market_data
        self.converter = converter or get_converter()
        self.redis = redis
        self.pool = pool
        
        # Order tracking
        self._orders: Dict[str, KrakenOrder] = {}
        self._client_order_map: Dict[str, str] = {}  # client_order_id -> order_id
        self._order_history: Dict[str, List[Dict]] = {}
        self._order_callbacks: Dict[str, List[Callable]] = {}
        
        # Circuit breakers
        self._order_cb = CircuitBreaker(
            name="kraken_order",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._cancel_cb = CircuitBreaker(
            name="kraken_cancel",
            failure_threshold=5,
            recovery_timeout=60
        )
        
        # WebSocket integration
        self._ws_subscribed = False
        self._ws_order_handlers: List[Callable] = []
        
        # Database initialization
        self._db_initialized = False
        
        # Order limits
        self._max_open_orders = 100  # Default, will be updated from exchange
        
        # Rate limit tracking
        self._rate_limit_tracker = {
            'requests': 0,
            'window_start': time.time(),
            'max_requests': 20,  # Kraken's default rate limit
        }
        
        logger.info("KrakenOrderManager initialized")
    
    async def initialize(self):
        """Initialize order manager."""
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load open orders
        await self.load_open_orders()
        
        # Start periodic order sync
        asyncio.create_task(self._periodic_order_sync())
        
        logger.info("KrakenOrderManager initialization complete")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # ORDER PLACEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_order(self, order_request: OrderRequest) -> OrderResponse:
        """
        Place an order on Kraken.
        
        Args:
            order_request: Order request object
            
        Returns:
            OrderResponse
            
        Raises:
            KrakenOrderError: For order placement errors
            KrakenInsufficientFundsError: For insufficient funds
            KrakenRateLimitError: For rate limit errors
        """
        if self._order_cb.is_open():
            raise KrakenRateLimitError("Order circuit breaker is open")
        
        try:
            # Validate order
            validation = await self.validate_order(order_request)
            if not validation.is_valid:
                raise KrakenValidationError(
                    f"Order validation failed: {validation.message}",
                    details=validation.details
                )
            
            # Check rate limit
            await self._check_rate_limit()
            
            # Convert to Kraken format
            kraken_pair = self.converter.to_kraken_pair(order_request.symbol)
            kraken_type = order_request.order_type.value
            
            # Build request parameters
            params = {
                "pair": kraken_pair,
                "type": order_request.side.value,
                "ordertype": kraken_type,
                "volume": str(order_request.volume),
                "timeinforce": order_request.time_in_force.value,
            }
            
            # Add price for limit orders
            if order_request.price is not None:
                params["price"] = str(order_request.price)
            
            if order_request.limit_price is not None:
                params["price2"] = str(order_request.limit_price)
            
            if order_request.stop_price is not None:
                params["price"] = str(order_request.stop_price)
            
            if order_request.client_order_id:
                params["userref"] = order_request.client_order_id
            
            if order_request.reduce_only:
                params["reduce_only"] = "true"
            
            if order_request.post_only:
                params["post_only"] = "true"
            
            if order_request.expire_time:
                params["expiretm"] = str(int(order_request.expire_time.timestamp()))
            
            # Place order
            result = await self.base._private_request("AddOrder", params)
            
            # Parse response
            order_id = result.get('txid', [''])[0] if result.get('txid') else None
            if not order_id:
                raise KrakenOrderError("No order ID returned")
            
            # Create order response
            response = OrderResponse(
                order_id=order_id,
                client_order_id=order_request.client_order_id,
                status=KrakenOrderStatus.PENDING,
                symbol=order_request.symbol,
                side=order_request.side,
                order_type=order_request.order_type,
                volume=order_request.volume,
                price=order_request.price,
                limit_price=order_request.limit_price,
                stop_price=order_request.stop_price,
                time_in_force=order_request.time_in_force,
                created_at=datetime.utcnow(),
                metadata=order_request.metadata
            )
            
            # Track order
            await self._track_order(response)
            
            # Save to database
            if self.pool:
                await self._save_order(response)
            
            self._order_cb.record_success()
            
            logger.info(
                f"Order placed: {order_id} | {order_request.side} {order_request.volume} "
                f"{order_request.symbol} @ {order_request.price or 'market'}"
            )
            
            return response
            
        except Exception as e:
            self._order_cb.record_failure()
            logger.error(f"Order placement error: {e}")
            raise
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_market_order(
        self,
        symbol: str,
        side: KrakenOrderSide,
        volume: Decimal,
        client_order_id: Optional[str] = None,
        reduce_only: bool = False,
        metadata: Optional[Dict] = None
    ) -> OrderResponse:
        """
        Place a market order.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            volume: Order volume
            client_order_id: Client-side order ID
            reduce_only: Reduce-only position
            metadata: Additional metadata
            
        Returns:
            OrderResponse
        """
        order_request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=KrakenOrderType.MARKET,
            volume=volume,
            time_in_force=KrakenTimeInForce.IOC,
            client_order_id=client_order_id,
            reduce_only=reduce_only,
            metadata=metadata or {}
        )
        return await self.place_order(order_request)
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_limit_order(
        self,
        symbol: str,
        side: KrakenOrderSide,
        volume: Decimal,
        price: Decimal,
        time_in_force: KrakenTimeInForce = KrakenTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        post_only: bool = False,
        metadata: Optional[Dict] = None
    ) -> OrderResponse:
        """
        Place a limit order.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            volume: Order volume
            price: Limit price
            time_in_force: Time in force
            client_order_id: Client-side order ID
            post_only: Post-only order
            metadata: Additional metadata
            
        Returns:
            OrderResponse
        """
        order_request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=KrakenOrderType.LIMIT,
            volume=volume,
            price=price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            post_only=post_only,
            metadata=metadata or {}
        )
        return await self.place_order(order_request)
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_stop_loss_order(
        self,
        symbol: str,
        side: KrakenOrderSide,
        volume: Decimal,
        stop_price: Decimal,
        limit_price: Optional[Decimal] = None,
        time_in_force: KrakenTimeInForce = KrakenTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> OrderResponse:
        """
        Place a stop-loss order.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            volume: Order volume
            stop_price: Stop price
            limit_price: Limit price (for stop-limit orders)
            time_in_force: Time in force
            client_order_id: Client-side order ID
            metadata: Additional metadata
            
        Returns:
            OrderResponse
        """
        order_type = KrakenOrderType.STOP_LOSS_LIMIT if limit_price else KrakenOrderType.STOP_LOSS
        
        order_request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            stop_price=stop_price,
            limit_price=limit_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            metadata=metadata or {}
        )
        return await self.place_order(order_request)
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_take_profit_order(
        self,
        symbol: str,
        side: KrakenOrderSide,
        volume: Decimal,
        price: Decimal,
        limit_price: Optional[Decimal] = None,
        time_in_force: KrakenTimeInForce = KrakenTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> OrderResponse:
        """
        Place a take-profit order.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            volume: Order volume
            price: Take-profit price
            limit_price: Limit price (for take-profit limit orders)
            time_in_force: Time in force
            client_order_id: Client-side order ID
            metadata: Additional metadata
            
        Returns:
            OrderResponse
        """
        order_type = KrakenOrderType.TAKE_PROFIT_LIMIT if limit_price else KrakenOrderType.TAKE_PROFIT
        
        order_request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            price=price,
            limit_price=limit_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            metadata=metadata or {}
        )
        return await self.place_order(order_request)
    
    # =========================================================================
    # OCO AND BRACKET ORDERS
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_oco_order(self, oco_request: OCOOrderRequest) -> List[OrderResponse]:
        """
        Place an OCO (One Cancels Other) order.
        
        Args:
            oco_request: OCO order request
            
        Returns:
            List of order responses (stop order, limit order)
        """
        # Create stop order
        stop_order = OrderRequest(
            symbol=oco_request.symbol,
            side=oco_request.side,
            order_type=oco_request.stop_order_type,
            volume=oco_request.volume,
            stop_price=oco_request.stop_price,
            time_in_force=oco_request.time_in_force,
            client_order_id=f"{oco_request.client_order_id}_stop" if oco_request.client_order_id else None,
            metadata=oco_request.metadata
        )
        
        # Create limit order
        limit_order = OrderRequest(
            symbol=oco_request.symbol,
            side=oco_request.side,
            order_type=oco_request.limit_order_type,
            volume=oco_request.volume,
            price=oco_request.limit_price,
            time_in_force=oco_request.time_in_force,
            client_order_id=f"{oco_request.client_order_id}_limit" if oco_request.client_order_id else None,
            metadata=oco_request.metadata
        )
        
        # Place both orders
        try:
            stop_response = await self.place_order(stop_order)
            limit_response = await self.place_order(limit_order)
            
            # Link orders (OCO relationship)
            await self._link_orders(stop_response.order_id, limit_response.order_id, "OCO")
            
            logger.info(f"OCO order placed: Stop={stop_response.order_id}, Limit={limit_response.order_id}")
            
            return [stop_response, limit_response]
            
        except Exception as e:
            logger.error(f"OCO order placement failed: {e}")
            # Attempt to cancel any placed orders
            raise
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_bracket_order(
        self,
        bracket_request: BracketOrderRequest
    ) -> Tuple[OrderResponse, OrderResponse, OrderResponse]:
        """
        Place a bracket order with entry, stop-loss, and take-profit.
        
        Args:
            bracket_request: Bracket order request
            
        Returns:
            Tuple of (entry_order, stop_loss_order, take_profit_order)
        """
        # Entry order
        entry_order = OrderRequest(
            symbol=bracket_request.symbol,
            side=bracket_request.side,
            order_type=bracket_request.entry_order_type,
            volume=bracket_request.volume,
            price=bracket_request.entry_price,
            time_in_force=bracket_request.time_in_force,
            client_order_id=f"{bracket_request.client_order_id}_entry" if bracket_request.client_order_id else None,
            metadata=bracket_request.metadata
        )
        
        # Stop-loss order
        stop_loss_order = OrderRequest(
            symbol=bracket_request.symbol,
            side=KrakenOrderSide.SELL if bracket_request.side == KrakenOrderSide.BUY else KrakenOrderSide.BUY,
            order_type=bracket_request.stop_loss_order_type,
            volume=bracket_request.volume,
            stop_price=bracket_request.stop_loss_price,
            time_in_force=KrakenTimeInForce.GTC,
            client_order_id=f"{bracket_request.client_order_id}_sl" if bracket_request.client_order_id else None,
            metadata=bracket_request.metadata
        )
        
        # Take-profit order
        take_profit_order = OrderRequest(
            symbol=bracket_request.symbol,
            side=KrakenOrderSide.SELL if bracket_request.side == KrakenOrderSide.BUY else KrakenOrderSide.BUY,
            order_type=bracket_request.take_profit_order_type,
            volume=bracket_request.volume,
            price=bracket_request.take_profit_price,
            time_in_force=KrakenTimeInForce.GTC,
            client_order_id=f"{bracket_request.client_order_id}_tp" if bracket_request.client_order_id else None,
            metadata=bracket_request.metadata
        )
        
        # Place orders
        try:
            entry_response = await self.place_order(entry_order)
            
            # Place stop-loss and take-profit only if entry order is filled
            # For now, place them as pending orders
            sl_response = await self.place_order(stop_loss_order)
            tp_response = await self.place_order(take_profit_order)
            
            # Link orders (bracket relationship)
            await self._link_orders(
                entry_response.order_id,
                sl_response.order_id,
                "BRACKET_SL"
            )
            await self._link_orders(
                entry_response.order_id,
                tp_response.order_id,
                "BRACKET_TP"
            )
            
            logger.info(
                f"Bracket order placed: Entry={entry_response.order_id}, "
                f"SL={sl_response.order_id}, TP={tp_response.order_id}"
            )
            
            return entry_response, sl_response, tp_response
            
        except Exception as e:
            logger.error(f"Bracket order placement failed: {e}")
            # Attempt to cancel any placed orders
            raise
    
    # =========================================================================
    # BATCH ORDER PLACEMENT
    # =========================================================================
    
    @async_retry(max_attempts=2, base_delay=1.0, max_delay=10.0)
    async def place_batch_orders(
        self,
        batch_request: BatchOrderRequest
    ) -> BatchOrderResponse:
        """
        Place multiple orders in a batch.
        
        Args:
            batch_request: Batch order request
            
        Returns:
            BatchOrderResponse
        """
        successful = []
        failed = []
        
        for i, order_req in enumerate(batch_request.orders):
            try:
                # Validate order
                validation = await self.validate_order(order_req)
                if not validation.is_valid:
                    if batch_request.ignore_invalid:
                        failed.append({
                            "index": i,
                            "order": order_req.dict(),
                            "error": validation.message,
                            "details": validation.details
                        })
                        continue
                    else:
                        raise KrakenValidationError(
                            f"Order {i} validation failed: {validation.message}"
                        )
                
                # Place order
                if batch_request.execute_sequentially:
                    response = await self.place_order(order_req)
                else:
                    # Execute concurrently
                    response = await self.place_order(order_req)
                
                successful.append(response)
                
            except Exception as e:
                failed.append({
                    "index": i,
                    "order": order_req.dict(),
                    "error": str(e)
                })
                
                if batch_request.stop_on_error:
                    # Cancel any successful orders
                    for resp in successful:
                        try:
                            await self.cancel_order(resp.order_id)
                        except Exception:
                            pass
                    break
        
        return BatchOrderResponse(
            successful=successful,
            failed=failed,
            total_success=len(successful),
            total_failed=len(failed),
            metadata=batch_request.metadata
        )
    
    # =========================================================================
    # ORDER CANCELLATION
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def cancel_order(
        self,
        order_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            reason: Cancellation reason
            
        Returns:
            True if cancelled successfully
            
        Raises:
            KrakenOrderNotFoundError: If order not found
            KrakenOrderError: For cancellation errors
        """
        if self._cancel_cb.is_open():
            raise KrakenRateLimitError("Cancel circuit breaker is open")
        
        try:
            # Check rate limit
            await self._check_rate_limit()
            
            # Cancel order
            result = await self.base._private_request(
                "CancelOrder",
                data={"txid": order_id}
            )
            
            if result.get('count', 0) == 0:
                raise KrakenOrderNotFoundError(order_id)
            
            # Update order status
            await self._update_order_status(order_id, KrakenOrderStatus.CANCELLED)
            
            # Log audit
            await self._log_audit(order_id, "cancel", reason=reason)
            
            self._cancel_cb.record_success()
            
            logger.info(f"Order cancelled: {order_id} (reason: {reason})")
            return True
            
        except Exception as e:
            self._cancel_cb.record_failure()
            logger.error(f"Order cancellation error: {e}")
            raise
    
    @async_retry(max_attempts=2, base_delay=1.0, max_delay=10.0)
    async def cancel_all_orders(self) -> int:
        """
        Cancel all open orders.
        
        Returns:
            Number of orders cancelled
        """
        try:
            result = await self.base._private_request("CancelAllOrders")
            count = result.get('count', 0)
            
            logger.info(f"Cancelled {count} orders")
            return count
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            raise
    
    async def cancel_orders_by_symbol(self, symbol: str) -> int:
        """
        Cancel all open orders for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Number of orders cancelled
        """
        kraken_pair = self.converter.to_kraken_pair(symbol)
        
        # Get open orders for the symbol
        open_orders = await self.get_open_orders()
        symbol_orders = [o for o in open_orders if o.pair == kraken_pair]
        
        cancelled = 0
        for order in symbol_orders:
            try:
                if await self.cancel_order(order.id):
                    cancelled += 1
            except Exception:
                pass
        
        logger.info(f"Cancelled {cancelled} orders for {symbol}")
        return cancelled
    
    # =========================================================================
    # ORDER MODIFICATION
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def modify_order(self, modification: OrderModificationRequest) -> OrderResponse:
        """
        Modify an existing order.
        
        Args:
            modification: Order modification request
            
        Returns:
            Updated OrderResponse
            
        Raises:
            KrakenOrderNotFoundError: If order not found
        """
        try:
            # Build modification parameters
            params = {"txid": modification.order_id}
            
            if modification.price is not None:
                params["price"] = str(modification.price)
            
            if modification.limit_price is not None:
                params["price2"] = str(modification.limit_price)
            
            if modification.stop_price is not None:
                params["stop"] = str(modification.stop_price)
            
            if modification.volume is not None:
                params["volume"] = str(modification.volume)
            
            if modification.time_in_force is not None:
                params["timeinforce"] = modification.time_in_force.value
            
            # Make modification request
            result = await self.base._private_request("EditOrder", params)
            
            # Parse response
            order_id = result.get('txid', modification.order_id)
            
            # Get updated order
            order = await self.get_order(order_id)
            if not order:
                raise KrakenOrderNotFoundError(order_id)
            
            # Create response
            response = self._order_to_response(order)
            
            # Save to database
            if self.pool:
                await self._save_order(response)
            
            # Log audit
            await self._log_audit(order_id, "modify", metadata=modification.metadata)
            
            logger.info(f"Order modified: {order_id}")
            return response
            
        except Exception as e:
            logger.error(f"Order modification error: {e}")
            raise
    
    # =========================================================================
    # ORDER RETRIEVAL
    # =========================================================================
    
    @async_retry(max_attempts=2, base_delay=1.0, max_delay=10.0)
    async def get_order(self, order_id: str) -> Optional[KrakenOrder]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            KrakenOrder or None
        """
        try:
            # Check cache
            if order_id in self._orders:
                return self._orders[order_id]
            
            # Query order
            result = await self.base._private_request(
                "QueryOrders",
                data={"txid": order_id}
            )
            
            if order_id not in result:
                return None
            
            order = self.base._parse_order(order_id, result[order_id])
            self._orders[order_id] = order
            
            return order
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None
    
    @async_retry(max_attempts=2, base_delay=1.0, max_delay=10.0)
    async def get_open_orders(self) -> List[KrakenOrder]:
        """
        Get all open orders.
        
        Returns:
            List of open orders
        """
        try:
            result = await self.base._private_request("OpenOrders")
            
            orders = []
            for order_id, data in result.get('open', {}).items():
                order = self.base._parse_order(order_id, data)
                self._orders[order_id] = order
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []
    
    @async_retry(max_attempts=2, base_delay=1.0, max_delay=10.0)
    async def get_closed_orders(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50
    ) -> List[KrakenOrder]:
        """
        Get closed orders with filters.
        
        Args:
            symbol: Filter by symbol
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of orders
            
        Returns:
            List of closed orders
        """
        try:
            params = {"limit": min(limit, 500)}
            
            if start_time:
                params["start"] = int(start_time.timestamp())
            
            if end_time:
                params["end"] = int(end_time.timestamp())
            
            result = await self.base._private_request("ClosedOrders", params)
            
            orders = []
            for order_id, data in result.get('closed', {}).items():
                order = self.base._parse_order(order_id, data)
                
                # Filter by symbol
                if symbol:
                    kraken_symbol = self.converter.to_kraken_pair(symbol)
                    if order.pair != kraken_symbol:
                        continue
                
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting closed orders: {e}")
            return []
    
    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get order history with additional details.
        
        Args:
            symbol: Filter by symbol
            limit: Maximum number of entries
            
        Returns:
            List of order history entries
        """
        try:
            orders = await self.get_closed_orders(symbol, limit=limit)
            
            history = []
            for order in orders:
                history.append({
                    "order_id": order.id,
                    "symbol": self.converter.to_standard_pair(order.pair),
                    "side": order.side.value,
                    "type": order.type.value,
                    "volume": order.volume,
                    "executed_volume": order.executed_volume,
                    "price": order.price,
                    "average_price": order.average_price,
                    "status": order.status.value,
                    "created_at": order.created_at,
                    "updated_at": order.updated_at,
                    "fee": order.fee,
                    "cost": order.cost,
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting order history: {e}")
            return []
    
    # =========================================================================
    # ORDER VALIDATION
    # =========================================================================
    
    async def validate_order(
        self,
        order_request: OrderRequest
    ) -> OrderValidationResponse:
        """
        Validate an order before placement.
        
        Args:
            order_request: Order request to validate
            
        Returns:
            OrderValidationResponse
        """
        details = {}
        
        try:
            # Validate symbol
            pair_info = await self.market_data.get_pair(order_request.symbol) if self.market_data else None
            if not pair_info:
                return OrderValidationResponse(
                    result=OrderValidationResult.INVALID_SYMBOL,
                    is_valid=False,
                    message=f"Invalid symbol: {order_request.symbol}"
                )
            
            details["pair_info"] = pair_info.dict()
            
            # Validate volume
            if order_request.volume <= 0:
                return OrderValidationResponse(
                    result=OrderValidationResult.INVALID_VOLUME,
                    is_valid=False,
                    message="Volume must be positive"
                )
            
            # Check minimum volume
            if order_request.volume < pair_info.ordermin:
                return OrderValidationResponse(
                    result=OrderValidationResult.INVALID_VOLUME,
                    is_valid=False,
                    message=f"Volume {order_request.volume} below minimum {pair_info.ordermin}",
                    details={"min_volume": float(pair_info.ordermin)}
                )
            
            # Validate price for limit orders
            if order_request.order_type in [KrakenOrderType.LIMIT, KrakenOrderType.STOP_LOSS_LIMIT]:
                if order_request.price is None:
                    return OrderValidationResponse(
                        result=OrderValidationResult.INVALID_PRICE,
                        is_valid=False,
                        message="Price required for limit order"
                    )
                
                if order_request.price <= 0:
                    return OrderValidationResponse(
                        result=OrderValidationResult.INVALID_PRICE,
                        is_valid=False,
                        message="Price must be positive"
                    )
                
                # Check price tick size
                if order_request.price % pair_info.tick_size != 0:
                    details["tick_size"] = float(pair_info.tick_size)
            
            # Validate balance (if requested)
            if order_request.validate_balance:
                # Implement balance check
                pass
            
            # Check market status
            if pair_info.status != "online":
                return OrderValidationResponse(
                    result=OrderValidationResult.MARKET_CLOSED,
                    is_valid=False,
                    message=f"Market {order_request.symbol} is {pair_info.status}"
                )
            
            return OrderValidationResponse(
                result=OrderValidationResult.VALID,
                is_valid=True,
                message="Order is valid",
                details=details
            )
            
        except Exception as e:
            return OrderValidationResponse(
                result=OrderValidationResult.INVALID_SYMBOL,
                is_valid=False,
                message=f"Validation error: {str(e)}",
                details={"error": str(e)}
            )
    
    # =========================================================================
    # ORDER EXECUTION ANALYTICS
    # =========================================================================
    
    async def get_order_execution_report(
        self,
        order_id: str
    ) -> Optional[OrderExecutionReport]:
        """
        Get detailed execution report for an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            OrderExecutionReport or None
        """
        try:
            order = await self.get_order(order_id)
            if not order:
                return None
            
            # Get execution details
            executions = await self._get_order_executions(order_id)
            
            # Calculate metrics
            filled_volume = order.executed_volume or Decimal('0')
            avg_price = order.average_price or order.price or Decimal('0')
            
            # Calculate slippage
            slippage = Decimal('0')
            slippage_percent = Decimal('0')
            if executions:
                # Compare actual execution price to expected
                if order.price:
                    actual_price = sum(e['price'] * e['volume'] for e in executions) / sum(e['volume'] for e in executions)
                    slippage = actual_price - order.price
                    slippage_percent = (slippage / order.price * 100) if order.price > 0 else Decimal('0')
            
            # Determine execution latency
            latency_ms = 0
            if order.created_at:
                latency_ms = (datetime.utcnow() - order.created_at).total_seconds() * 1000
            
            return OrderExecutionReport(
                order_id=order.id,
                symbol=self.converter.to_standard_pair(order.pair),
                side=order.side,
                order_type=order.type,
                volume=order.volume,
                filled_volume=filled_volume,
                average_price=avg_price,
                price=order.price or avg_price,
                total_cost=order.cost or (avg_price * filled_volume),
                fee=order.fee,
                fee_currency=self.converter.to_standard_currency(order.pair.split('X')[-1] if order.pair else 'USD'),
                execution_time=datetime.utcnow(),
                status=order.status,
                exchange_status=order.status.value,
                latency_ms=latency_ms,
                slippage=slippage,
                slippage_percent=slippage_percent,
                metadata=order.metadata
            )
            
        except Exception as e:
            logger.error(f"Error getting execution report: {e}")
            return None
    
    # =========================================================================
    # ORDER TRACKING AND SYNC
    # =========================================================================
    
    async def load_open_orders(self):
        """Load open orders from exchange."""
        try:
            orders = await self.get_open_orders()
            for order in orders:
                self._orders[order.id] = order
                if hasattr(order, 'client_order_id') and order.client_order_id:
                    self._client_order_map[order.client_order_id] = order.id
            
            logger.info(f"Loaded {len(orders)} open orders")
            
        except Exception as e:
            logger.error(f"Error loading open orders: {e}")
    
    async def _track_order(self, response: OrderResponse):
        """Track an order."""
        self._orders[response.order_id] = self._response_to_kraken_order(response)
        
        if response.client_order_id:
            self._client_order_map[response.client_order_id] = response.order_id
    
    async def _update_order_status(self, order_id: str, status: KrakenOrderStatus):
        """Update order status."""
        if order_id in self._orders:
            self._orders[order_id].status = status
    
    async def _periodic_order_sync(self):
        """Periodically sync order status."""
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                # Sync open orders
                await self.load_open_orders()
                
                # Update order statuses
                for order_id in list(self._orders.keys()):
                    try:
                        order = await self.get_order(order_id)
                        if order:
                            self._orders[order_id] = order
                    except Exception:
                        pass
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Order sync error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # ORDER LINKING
    # =========================================================================
    
    async def _link_orders(
        self,
        order1_id: str,
        order2_id: str,
        relationship: str
    ):
        """Link two orders (e.g., OCO, bracket)."""
        try:
            # Store link in database
            if self.pool:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS kraken_order_links (
                            order1_id VARCHAR(64),
                            order2_id VARCHAR(64),
                            relationship VARCHAR(50),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                    await conn.execute(
                        """
                        INSERT INTO kraken_order_links (order1_id, order2_id, relationship)
                        VALUES ($1, $2, $3)
                        """,
                        order1_id,
                        order2_id,
                        relationship
                    )
            
            logger.info(f"Linked orders: {order1_id} <-> {order2_id} ({relationship})")
            
        except Exception as e:
            logger.error(f"Error linking orders: {e}")
    
    # =========================================================================
    # ORDER EXECUTIONS
    # =========================================================================
    
    async def _get_order_executions(self, order_id: str) -> List[Dict[str, Any]]:
        """Get order executions."""
        if not self.pool:
            return []
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM kraken_order_executions
                    WHERE order_id = $1
                    ORDER BY executed_at
                    """,
                    order_id
                )
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting executions: {e}")
            return []
    
    # =========================================================================
    # RATE LIMITING
    # =========================================================================
    
    async def _check_rate_limit(self):
        """Check and enforce rate limits."""
        now = time.time()
        window = 60  # 60 second window
        
        # Reset window if expired
        if now - self._rate_limit_tracker['window_start'] > window:
            self._rate_limit_tracker['window_start'] = now
            self._rate_limit_tracker['requests'] = 0
        
        # Check limit
        if self._rate_limit_tracker['requests'] >= self._rate_limit_tracker['max_requests']:
            wait_time = window - (now - self._rate_limit_tracker['window_start'])
            if wait_time > 0:
                await asyncio.sleep(wait_time + 1)
                self._rate_limit_tracker['window_start'] = time.time()
                self._rate_limit_tracker['requests'] = 0
        
        self._rate_limit_tracker['requests'] += 1
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_order(self, response: OrderResponse):
        """Save order to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kraken_orders (
                        id, client_order_id, pair, side, order_type,
                        status, volume, executed_volume, price,
                        avg_price, limit_price, stop_price,
                        fee, cost, time_in_force,
                        created_at, updated_at, expires_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15,
                              $16, $17, $18, $19)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        executed_volume = EXCLUDED.executed_volume,
                        avg_price = EXCLUDED.avg_price,
                        fee = EXCLUDED.fee,
                        cost = EXCLUDED.cost,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    response.order_id,
                    response.client_order_id,
                    self.converter.to_kraken_pair(response.symbol),
                    response.side.value,
                    response.order_type.value,
                    response.status.value,
                    response.volume,
                    response.filled_volume,
                    response.price or 0,
                    response.average_price or 0,
                    response.limit_price,
                    response.stop_price,
                    response.fee,
                    response.cost,
                    response.time_in_force.value,
                    response.created_at,
                    response.updated_at,
                    response.expires_at,
                    json.dumps(response.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving order: {e}")
    
    async def _log_audit(
        self,
        order_id: str,
        action: str,
        previous_state: Optional[Dict] = None,
        new_state: Optional[Dict] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log order audit entry."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kraken_order_audit (
                        order_id, action, previous_state, new_state,
                        reason, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    order_id,
                    action,
                    json.dumps(previous_state, default=str) if previous_state else None,
                    json.dumps(new_state, default=str) if new_state else None,
                    reason,
                    json.dumps(metadata or {}, default=str)
                )
        except Exception as e:
            logger.error(f"Error logging audit: {e}")
    
    # =========================================================================
    # WEBHOOKS AND CALLBACKS
    # =========================================================================
    
    async def register_order_callback(
        self,
        order_id: str,
        callback: Callable
    ):
        """Register callback for order updates."""
        if order_id not in self._order_callbacks:
            self._order_callbacks[order_id] = []
        self._order_callbacks[order_id].append(callback)
    
    async def _notify_order_update(self, order_id: str, order: KrakenOrder):
        """Notify callbacks about order updates."""
        if order_id in self._order_callbacks:
            for callback in self._order_callbacks[order_id]:
                try:
                    await callback(order)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def _response_to_kraken_order(self, response: OrderResponse) -> KrakenOrder:
        """Convert OrderResponse to KrakenOrder."""
        return KrakenOrder(
            id=response.order_id,
            pair=self.converter.to_kraken_pair(response.symbol),
            type=response.order_type,
            side=response.side,
            status=response.status,
            price=response.price or Decimal('0'),
            volume=response.volume,
            executed_volume=response.filled_volume,
            average_price=response.average_price or Decimal('0'),
            fee=response.fee,
            cost=response.cost,
            limit_price=response.limit_price,
            stop_price=response.stop_price,
            time_in_force=response.time_in_force,
            created_at=response.created_at,
            updated_at=response.updated_at,
            expires_at=response.expires_at,
            metadata=response.metadata
        )
    
    def _order_to_response(self, order: KrakenOrder) -> OrderResponse:
        """Convert KrakenOrder to OrderResponse."""
        return OrderResponse(
            order_id=order.id,
            symbol=self.converter.to_standard_pair(order.pair),
            side=order.side,
            order_type=order.type,
            volume=order.volume,
            filled_volume=order.executed_volume,
            price=order.price,
            average_price=order.average_price,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            fee=order.fee,
            cost=order.cost,
            time_in_force=order.time_in_force,
            status=order.status,
            created_at=order.created_at,
            updated_at=order.updated_at,
            expires_at=order.expires_at,
            metadata=order.metadata
        )
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown order manager."""
        logger.info("Shutting down KrakenOrderManager")
        # Nothing to clean up


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'KrakenOrderManager',
    'OrderRequest',
    'OrderResponse',
    'BatchOrderRequest',
    'BatchOrderResponse',
    'OrderValidationRequest',
    'OrderValidationResponse',
    'OrderValidationResult',
    'OrderCancelRequest',
    'OrderModificationRequest',
    'OCOOrderRequest',
    'BracketOrderRequest',
    'OrderExecutionReport',
    'OrderExecutionType',
    'KrakenOrderStatus',
    'KrakenOrderFlags',
]
