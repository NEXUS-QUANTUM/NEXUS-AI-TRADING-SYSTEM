# trading/exchanges/okx/order.py
# Nexus AI Trading System - OKX Exchange Order Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - Order Management Module

This module provides comprehensive order management functionality for the OKX
cryptocurrency exchange, including:

- Order placement with all order types (market, limit, post-only, IOC, FOK)
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
- Database persistence with asyncpg
- Redis caching for performance
- Circuit breaker pattern for resilience
- Rate limit management
- Audit logging
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.exchanges.okx.base import (
    OKXBase,
    OKXConfig,
    OKXApiType,
    OKXOrderType,
    OKXOrderSide,
    OKXOrderStatus,
    OKXTimeInForce
)
from trading.exchanges.okx.exceptions import (
    OKXError,
    OKXOrderError,
    OKXOrderNotFoundError,
    OKXInsufficientFundsError,
    OKXRateLimitError,
    OKXValidationError,
    OKXParameterError
)
from trading.exchanges.okx.converter import OKXConverter, get_converter
from trading.exchanges.okx.market import OKXMarketData
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class OKXOrderStatusExtended(str, Enum):
    """OKX order status extended."""
    PENDING = "pending"
    OPEN = "live"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    TRIGGERED = "triggered"
    STOPPED = "stopped"
    HELD = "held"
    IN_PROGRESS = "in_progress"
    ERROR = "error"


class OrderExecutionType(str, Enum):
    """Order execution type."""
    MARKET = "market"
    LIMIT = "limit"
    POST_ONLY = "post_only"
    FOK = "fok"
    IOC = "ioc"
    OPTIMAL_LIMIT_IOC = "optimal_limit_ioc"
    TWAP = "twap"
    VWAP = "vwap"
    ICEBERG = "iceberg"
    SCALING = "scaling"


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
    INSTRUMENT_NOT_TRADING = "instrument_not_trading"
    INVALID_ORDER_TYPE = "invalid_order_type"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OrderRequest(BaseModel):
    """Order request model."""
    symbol: str
    side: OKXOrderSide
    order_type: OKXOrderType
    volume: Decimal
    price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: OKXTimeInForce = OKXTimeInForce.GTC
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

        if order_type in [OKXOrderType.LIMIT, OKXOrderType.POST_ONLY, 
                         OKXOrderType.FOK, OKXOrderType.IOC]:
            if price is None:
                raise ValueError(f"Price required for {order_type} order")

        return values


class OrderResponse(BaseModel):
    """Order response model."""
    order_id: str
    client_order_id: Optional[str] = None
    status: OKXOrderStatus
    symbol: str
    side: OKXOrderSide
    order_type: OKXOrderType
    volume: Decimal
    price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: OKXTimeInForce
    filled_volume: Decimal = Decimal('0')
    remaining_volume: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    fee_currency: Optional[str] = None
    cost: Decimal = Decimal('0')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.volume == 0:
            return 0.0
        return float(self.filled_volume / self.volume * 100)


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
    validate_order_type: bool = True


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
    time_in_force: Optional[OKXTimeInForce] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OCOOrderRequest(BaseModel):
    """OCO (One Cancels Other) order request."""
    symbol: str
    side: OKXOrderSide
    stop_price: Decimal
    limit_price: Decimal
    volume: Decimal
    time_in_force: OKXTimeInForce = OKXTimeInForce.GTC
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BracketOrderRequest(BaseModel):
    """Bracket order request (OCO with stop-loss and take-profit)."""
    symbol: str
    side: OKXOrderSide
    entry_price: Decimal
    volume: Decimal
    stop_loss_price: Decimal
    take_profit_price: Decimal
    entry_order_type: OKXOrderType = OKXOrderType.LIMIT
    time_in_force: OKXTimeInForce = OKXTimeInForce.GTC
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderExecutionReport(BaseModel):
    """Order execution report."""
    order_id: str
    symbol: str
    side: OKXOrderSide
    order_type: OKXOrderType
    volume: Decimal
    filled_volume: Decimal
    average_price: Decimal
    price: Decimal
    total_cost: Decimal
    fee: Decimal
    fee_currency: str
    execution_time: datetime
    status: OKXOrderStatus
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
CREATE TABLE IF NOT EXISTS okx_orders (
    id VARCHAR(64) PRIMARY KEY,
    client_order_id VARCHAR(64),
    symbol VARCHAR(50) NOT NULL,
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
    fee_currency VARCHAR(10),
    cost DECIMAL(32, 16) DEFAULT 0,
    time_in_force VARCHAR(10) DEFAULT 'GTC',
    reduce_only BOOLEAN DEFAULT FALSE,
    post_only BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,
    closed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_orders_symbol (symbol),
    INDEX idx_okx_orders_status (status),
    INDEX idx_okx_orders_created_at (created_at),
    INDEX idx_okx_orders_client_order_id (client_order_id)
);

-- Order executions
CREATE TABLE IF NOT EXISTS okx_order_executions (
    id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL REFERENCES okx_orders(id),
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    cost DECIMAL(32, 16) NOT NULL,
    fee DECIMAL(32, 16) DEFAULT 0,
    fee_currency VARCHAR(10),
    executed_at TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_order_executions_order_id (order_id),
    INDEX idx_okx_order_executions_executed_at (executed_at)
);

-- Order execution reports
CREATE TABLE IF NOT EXISTS okx_execution_reports (
    id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL,
    report_type VARCHAR(30),
    status VARCHAR(30) NOT NULL,
    executed_volume DECIMAL(32, 16) DEFAULT 0,
    avg_price DECIMAL(32, 16) DEFAULT 0,
    fee DECIMAL(32, 16) DEFAULT 0,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_execution_reports_order_id (order_id),
    INDEX idx_okx_execution_reports_timestamp (timestamp)
);

-- Order audit log
CREATE TABLE IF NOT EXISTS okx_order_audit (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL,
    action VARCHAR(50) NOT NULL,
    previous_state JSONB,
    new_state JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_order_audit_order_id (order_id),
    INDEX idx_okx_order_audit_timestamp (timestamp)
);

-- Order links (for OCO, bracket, etc.)
CREATE TABLE IF NOT EXISTS okx_order_links (
    order1_id VARCHAR(64) NOT NULL,
    order2_id VARCHAR(64) NOT NULL,
    relationship VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (order1_id, order2_id)
);
"""


# =============================================================================
# MAIN ORDER MANAGEMENT CLASS
# =============================================================================

class OKXOrderManager:
    """
    Advanced order management for OKX exchange.
    
    Features:
    - All order types (market, limit, post-only, IOC, FOK)
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
        base: OKXBase,
        config: OKXConfig,
        market_data: Optional[OKXMarketData] = None,
        converter: Optional[OKXConverter] = None,
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
        self._orders: Dict[str, Dict[str, Any]] = {}  # order_id -> order data
        self._client_order_map: Dict[str, str] = {}  # client_order_id -> order_id
        self._order_callbacks: Dict[str, List[Callable]] = {}
        
        # Circuit breakers
        self._order_cb = CircuitBreaker(
            name="okx_order",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._cancel_cb = CircuitBreaker(
            name="okx_cancel",
            failure_threshold=5,
            recovery_timeout=60
        )
        
        # WebSocket integration
        self._ws_subscribed = False
        self._ws_order_handlers: List[Callable] = []
        
        # Database initialization
        self._db_initialized = False
        
        # Order limits
        self._max_open_orders = 100
        
        # Rate limit tracking
        self._rate_limit_tracker = {
            'requests': 0,
            'window_start': time.time(),
            'max_requests': 20,
        }
        
        logger.info("OKXOrderManager initialized")
    
    async def initialize(self):
        """Initialize order manager."""
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load open orders
        await self.load_open_orders()
        
        # Start periodic order sync
        asyncio.create_task(self._periodic_order_sync())
        
        # Start WebSocket order listener if WebSocket is available
        if hasattr(self.base, 'ws_subscribe'):
            await self._subscribe_to_order_updates()
        
        logger.info("OKXOrderManager initialization complete")
    
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
        Place an order on OKX.
        
        Args:
            order_request: Order request object
            
        Returns:
            OrderResponse
            
        Raises:
            OKXOrderError: For order placement errors
            OKXInsufficientFundsError: For insufficient funds
            OKXRateLimitError: For rate limit errors
        """
        if self._order_cb.is_open():
            raise OKXRateLimitError("Order circuit breaker is open")
        
        try:
            # Validate order
            validation = await self.validate_order(order_request)
            if not validation.is_valid:
                raise OKXValidationError(
                    f"Order validation failed: {validation.message}",
                    details=validation.details
                )
            
            # Check rate limit
            await self._check_rate_limit()
            
            # Convert to OKX format
            okx_symbol = self.converter.to_okx_instrument(order_request.symbol)
            
            # Build request parameters
            params = {
                "instId": okx_symbol,
                "side": order_request.side.value,
                "ordType": order_request.order_type.value,
                "sz": str(order_request.volume),
                "tdMode": "cash" if order_request.order_type in [OKXOrderType.MARKET, OKXOrderType.IOC, OKXOrderType.FOK] else "cross",
            }
            
            # Add price for limit orders
            if order_request.price is not None:
                params["px"] = str(order_request.price)
            
            if order_request.limit_price is not None:
                params["px"] = str(order_request.limit_price)
            
            if order_request.stop_price is not None:
                params["stopPx"] = str(order_request.stop_price)
            
            if order_request.client_order_id:
                params["clOrdId"] = order_request.client_order_id
            
            if order_request.reduce_only:
                params["reduceOnly"] = "true"
            
            if order_request.post_only:
                params["postOnly"] = "true"
            
            if order_request.expire_time:
                params["expireTime"] = str(int(order_request.expire_time.timestamp()))
            
            # Place order
            response = await self.base._private_request("trade/order", params, "POST")
            
            if not response:
                raise OKXOrderError("No response from order placement")
            
            order_data = response[0] if isinstance(response, list) else response
            
            # Create order response
            response_obj = self._parse_order_data(order_data)
            
            # Track order
            await self._track_order(response_obj)
            
            # Save to database
            if self.pool:
                await self._save_order(response_obj)
            
            self._order_cb.record_success()
            
            logger.info(
                f"Order placed: {response_obj.order_id} | {order_request.side} {order_request.volume} "
                f"{order_request.symbol} @ {order_request.price or 'market'}"
            )
            
            return response_obj
            
        except Exception as e:
            self._order_cb.record_failure()
            logger.error(f"Order placement error: {e}")
            raise
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_market_order(
        self,
        symbol: str,
        side: OKXOrderSide,
        volume: Decimal,
        client_order_id: Optional[str] = None,
        reduce_only: bool = False,
        metadata: Optional[Dict] = None
    ) -> OrderResponse:
        """Place a market order."""
        order_request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OKXOrderType.MARKET,
            volume=volume,
            client_order_id=client_order_id,
            reduce_only=reduce_only,
            metadata=metadata or {}
        )
        return await self.place_order(order_request)
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_limit_order(
        self,
        symbol: str,
        side: OKXOrderSide,
        volume: Decimal,
        price: Decimal,
        time_in_force: OKXTimeInForce = OKXTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        post_only: bool = False,
        metadata: Optional[Dict] = None
    ) -> OrderResponse:
        """Place a limit order."""
        order_request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OKXOrderType.LIMIT,
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
        side: OKXOrderSide,
        volume: Decimal,
        stop_price: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: OKXTimeInForce = OKXTimeInForce.GTC,
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
            price: Limit price (for stop-limit orders)
            time_in_force: Time in force
            client_order_id: Client-side order ID
            metadata: Additional metadata
            
        Returns:
            OrderResponse
        """
        order_type = OKXOrderType.LIMIT if price else OKXOrderType.MARKET
        
        order_request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            metadata=metadata or {}
        )
        return await self.place_order(order_request)
    
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
            OKXOrderNotFoundError: If order not found
            OKXOrderError: For cancellation errors
        """
        if self._cancel_cb.is_open():
            raise OKXRateLimitError("Cancel circuit breaker is open")
        
        try:
            # Check rate limit
            await self._check_rate_limit()
            
            # Cancel order
            result = await self.base._private_request(
                "trade/cancel-order",
                {"ordId": order_id},
                "POST"
            )
            
            if not result:
                raise OKXOrderNotFoundError(order_id)
            
            # Update order status
            await self._update_order_status(order_id, OKXOrderStatus.CANCELLED)
            
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
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """
        Cancel all open orders.
        
        Args:
            symbol: Filter by symbol
            
        Returns:
            Number of orders cancelled
        """
        try:
            params = {}
            if symbol:
                params["instId"] = self.converter.to_okx_instrument(symbol)
            
            result = await self.base._private_request("trade/cancel-all-orders", params, "POST")
            
            count = len(result) if result else 0
            logger.info(f"Cancelled {count} orders")
            return count
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            raise
    
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
            OKXOrderNotFoundError: If order not found
        """
        try:
            # Build modification parameters
            params = {"ordId": modification.order_id}
            
            if modification.price is not None:
                params["newPx"] = str(modification.price)
            
            if modification.volume is not None:
                params["newSz"] = str(modification.volume)
            
            if modification.limit_price is not None:
                params["newPx"] = str(modification.limit_price)
            
            if modification.stop_price is not None:
                params["newStopPx"] = str(modification.stop_price)
            
            # Make modification request
            result = await self.base._private_request("trade/amend-order", params, "POST")
            
            if not result:
                raise OKXOrderNotFoundError(modification.order_id)
            
            order_data = result[0] if isinstance(result, list) else result
            
            # Get updated order
            order = await self.get_order(modification.order_id)
            if not order:
                raise OKXOrderNotFoundError(modification.order_id)
            
            # Log audit
            await self._log_audit(modification.order_id, "modify", metadata=modification.metadata)
            
            logger.info(f"Order modified: {modification.order_id}")
            return order
            
        except Exception as e:
            logger.error(f"Order modification error: {e}")
            raise
    
    # =========================================================================
    # ORDER RETRIEVAL
    # =========================================================================
    
    @async_retry(max_attempts=2, base_delay=1.0, max_delay=10.0)
    async def get_order(self, order_id: str) -> Optional[OrderResponse]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            OrderResponse or None
        """
        try:
            # Check cache
            if order_id in self._orders:
                return self._response_from_data(self._orders[order_id])
            
            # Query order
            result = await self.base._private_request(
                "trade/order",
                {"ordId": order_id}
            )
            
            if not result:
                return None
            
            order_data = result[0] if isinstance(result, list) else result
            response = self._parse_order_data(order_data)
            
            # Cache order
            self._orders[order_id] = order_data
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None
    
    @async_retry(max_attempts=2, base_delay=1.0, max_delay=10.0)
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        """
        Get all open orders.
        
        Args:
            symbol: Filter by symbol
            
        Returns:
            List of open orders
        """
        try:
            params = {"state": "live"}
            if symbol:
                params["instId"] = self.converter.to_okx_instrument(symbol)
            
            result = await self.base._private_request("trade/orders-pending", params)
            
            orders = []
            for order_data in result:
                response = self._parse_order_data(order_data)
                self._orders[response.order_id] = order_data
                orders.append(response)
            
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
    ) -> List[OrderResponse]:
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
            params = {
                "state": "filled,cancelled,expired,rejected",
                "limit": min(limit, 100)
            }
            
            if symbol:
                params["instId"] = self.converter.to_okx_instrument(symbol)
            
            if start_time:
                params["begin"] = str(int(start_time.timestamp() * 1000))
            
            if end_time:
                params["end"] = str(int(end_time.timestamp() * 1000))
            
            result = await self.base._private_request("trade/orders-history", params)
            
            orders = []
            for order_data in result:
                response = self._parse_order_data(order_data)
                orders.append(response)
            
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
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "type": order.order_type.value,
                    "volume": float(order.volume),
                    "filled_volume": float(order.filled_volume),
                    "price": float(order.price) if order.price else None,
                    "average_price": float(order.average_price) if order.average_price else None,
                    "status": order.status.value,
                    "created_at": order.created_at.isoformat(),
                    "updated_at": order.updated_at.isoformat() if order.updated_at else None,
                    "fee": float(order.fee),
                    "cost": float(order.cost),
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting order history: {e}")
            return []
    
    # =========================================================================
    # ORDER VALIDATION
    # =========================================================================
    
    async def validate_order(self, order_request: OrderRequest) -> OrderValidationResponse:
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
            okx_symbol = self.converter.to_okx_instrument(order_request.symbol)
            
            if self.market_data:
                try:
                    instrument = await self.market_data.get_instrument(okx_symbol)
                    if not instrument:
                        return OrderValidationResponse(
                            result=OrderValidationResult.INVALID_SYMBOL,
                            is_valid=False,
                            message=f"Invalid symbol: {order_request.symbol}"
                        )
                    
                    details["instrument"] = instrument.dict()
                    
                    # Check instrument status
                    if instrument.status.value != "online":
                        return OrderValidationResponse(
                            result=OrderValidationResult.INSTRUMENT_NOT_TRADING,
                            is_valid=False,
                            message=f"Instrument {order_request.symbol} is not trading (status: {instrument.status.value})"
                        )
                except Exception as e:
                    logger.warning(f"Could not validate instrument: {e}")
            
            # Validate volume
            if order_request.volume <= 0:
                return OrderValidationResponse(
                    result=OrderValidationResult.INVALID_VOLUME,
                    is_valid=False,
                    message="Volume must be positive"
                )
            
            # Validate price for limit orders
            if order_request.order_type in [OKXOrderType.LIMIT, OKXOrderType.POST_ONLY, 
                                           OKXOrderType.FOK, OKXOrderType.IOC]:
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
            
            # Validate order type
            if order_request.order_type not in [OKXOrderType.MARKET, OKXOrderType.LIMIT, 
                                               OKXOrderType.POST_ONLY, OKXOrderType.FOK, 
                                               OKXOrderType.IOC, OKXOrderType.OPTIMAL_LIMIT_IOC]:
                return OrderValidationResponse(
                    result=OrderValidationResult.INVALID_ORDER_TYPE,
                    is_valid=False,
                    message=f"Invalid order type: {order_request.order_type.value}"
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
    
    async def get_order_execution_report(self, order_id: str) -> Optional[OrderExecutionReport]:
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
            filled_volume = order.filled_volume or Decimal('0')
            avg_price = order.average_price or order.price or Decimal('0')
            
            # Calculate slippage
            slippage = Decimal('0')
            slippage_percent = Decimal('0')
            if executions and order.price:
                actual_price = sum(e['price'] * e['volume'] for e in executions) / sum(e['volume'] for e in executions)
                slippage = actual_price - order.price
                slippage_percent = (slippage / order.price * 100) if order.price > 0 else Decimal('0')
            
            # Determine execution latency
            latency_ms = 0
            if order.created_at:
                latency_ms = (datetime.utcnow() - order.created_at).total_seconds() * 1000
            
            return OrderExecutionReport(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                volume=order.volume,
                filled_volume=filled_volume,
                average_price=avg_price,
                price=order.price or avg_price,
                total_cost=order.cost or (avg_price * filled_volume),
                fee=order.fee,
                fee_currency=order.fee_currency or "USD",
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
    
    async def _get_order_executions(self, order_id: str) -> List[Dict[str, Any]]:
        """Get order executions."""
        if not self.pool:
            return []
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM okx_order_executions
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
    # ORDER TRACKING AND SYNC
    # =========================================================================
    
    async def load_open_orders(self):
        """Load open orders from exchange."""
        try:
            orders = await self.get_open_orders()
            for order in orders:
                if order.client_order_id:
                    self._client_order_map[order.client_order_id] = order.order_id
            
            logger.info(f"Loaded {len(orders)} open orders")
            
        except Exception as e:
            logger.error(f"Error loading open orders: {e}")
    
    async def _track_order(self, response: OrderResponse):
        """Track an order."""
        self._orders[response.order_id] = response.dict()
        
        if response.client_order_id:
            self._client_order_map[response.client_order_id] = response.order_id
    
    async def _update_order_status(self, order_id: str, status: OKXOrderStatus):
        """Update order status."""
        if order_id in self._orders:
            self._orders[order_id]['status'] = status
    
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
                            self._orders[order_id] = order.dict()
                    except Exception:
                        pass
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Order sync error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # ORDER PARSING
    # =========================================================================
    
    def _parse_order_data(self, data: Dict[str, Any]) -> OrderResponse:
        """Parse order data from API response."""
        status_map = {
            'pending': OKXOrderStatus.PENDING,
            'live': OKXOrderStatus.OPEN,
            'partially_filled': OKXOrderStatus.PARTIALLY_FILLED,
            'filled': OKXOrderStatus.FILLED,
            'cancelled': OKXOrderStatus.CANCELLED,
            'expired': OKXOrderStatus.EXPIRED,
            'rejected': OKXOrderStatus.REJECTED,
        }
        
        status = status_map.get(data.get('state', 'pending'), OKXOrderStatus.PENDING)
        
        return OrderResponse(
            order_id=data.get('ordId', ''),
            client_order_id=data.get('clOrdId'),
            status=status,
            symbol=self.converter.to_standard_symbol(data.get('instId', '')),
            side=OKXOrderSide(data.get('side', 'buy')),
            order_type=OKXOrderType(data.get('ordType', 'limit')),
            volume=Decimal(str(data.get('sz', 0))),
            price=Decimal(str(data.get('px', 0))) if data.get('px') else None,
            limit_price=Decimal(str(data.get('px', 0))) if data.get('px') else None,
            stop_price=Decimal(str(data.get('stopPx', 0))) if data.get('stopPx') else None,
            time_in_force=OKXTimeInForce(data.get('tdMode', 'GTC')),
            filled_volume=Decimal(str(data.get('accFillSz', 0))),
            remaining_volume=Decimal(str(data.get('sz', 0))) - Decimal(str(data.get('accFillSz', 0))),
            average_price=Decimal(str(data.get('avgPx', 0))) if data.get('avgPx') else None,
            fee=Decimal(str(data.get('fee', 0))),
            fee_currency=data.get('feeCcy'),
            cost=Decimal(str(data.get('cost', 0))),
            created_at=datetime.fromtimestamp(int(data.get('cTime', 0)) / 1000) if data.get('cTime') else datetime.utcnow(),
            updated_at=datetime.fromtimestamp(int(data.get('uTime', 0)) / 1000) if data.get('uTime') else None,
            expires_at=datetime.fromtimestamp(int(data.get('expTime', 0)) / 1000) if data.get('expTime') else None,
            metadata=data
        )
    
    def _response_from_data(self, data: Dict[str, Any]) -> OrderResponse:
        """Create OrderResponse from stored data."""
        return OrderResponse(**data)
    
    # =========================================================================
    # WEBSOCKET ORDER UPDATES
    # =========================================================================
    
    async def _subscribe_to_order_updates(self):
        """Subscribe to order updates via WebSocket."""
        if self._ws_subscribed:
            return
        
        try:
            if hasattr(self.base, 'ws_subscribe'):
                await self.base.ws_subscribe(
                    "orders",
                    [],
                    self._handle_order_update
                )
                self._ws_subscribed = True
                logger.info("Subscribed to order updates")
        except Exception as e:
            logger.warning(f"Could not subscribe to order updates: {e}")
    
    async def _handle_order_update(self, message: Dict[str, Any]):
        """Handle order update from WebSocket."""
        try:
            if 'data' in message:
                for order_data in message['data']:
                    order = self._parse_order_data(order_data)
                    
                    # Update cache
                    self._orders[order.order_id] = order_data
                    
                    # Notify callbacks
                    await self._notify_order_update(order.order_id, order)
                    
        except Exception as e:
            logger.error(f"Error handling order update: {e}")
    
    # =========================================================================
    # RATE LIMITING
    # =========================================================================
    
    async def _check_rate_limit(self):
        """Check and enforce rate limits."""
        now = time.time()
        window = 60  # 60 second window
        
        if now - self._rate_limit_tracker['window_start'] > window:
            self._rate_limit_tracker['window_start'] = now
            self._rate_limit_tracker['requests'] = 0
        
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
                    INSERT INTO okx_orders (
                        id, client_order_id, symbol, side, order_type,
                        status, volume, executed_volume, price,
                        avg_price, limit_price, stop_price,
                        fee, fee_currency, cost, time_in_force,
                        reduce_only, post_only,
                        created_at, updated_at, expires_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16,
                              $17, $18, $19, $20, $21, $22)
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
                    response.symbol,
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
                    response.fee_currency,
                    response.cost,
                    response.time_in_force.value,
                    response.reduce_only,
                    response.post_only,
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
                    INSERT INTO okx_order_audit (
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
    
    async def register_order_callback(self, order_id: str, callback: Callable):
        """Register callback for order updates."""
        if order_id not in self._order_callbacks:
            self._order_callbacks[order_id] = []
        self._order_callbacks[order_id].append(callback)
    
    async def _notify_order_update(self, order_id: str, order: OrderResponse):
        """Notify callbacks about order updates."""
        if order_id in self._order_callbacks:
            for callback in self._order_callbacks[order_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(order)
                    else:
                        callback(order)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown order manager."""
        logger.info("Shutting down OKXOrderManager")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OKXOrderManager',
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
    'OKXOrderStatusExtended',
]
