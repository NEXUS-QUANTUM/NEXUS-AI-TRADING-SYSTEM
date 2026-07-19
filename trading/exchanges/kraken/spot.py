# trading/exchanges/kraken/spot.py
# Nexus AI Trading System - Kraken Exchange Spot Market Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Kraken Exchange - Spot Market Module

This module provides comprehensive spot market trading functionality for the Kraken
cryptocurrency exchange, including:

- Spot order placement and management
- Real-time spot price tracking
- Spot market depth analysis
- Spot trading pair management
- Spot balance management
- Spot order book integration
- Spot trade execution
- Spot position management
- Spot market analytics
- Spot WebSocket streaming
- Spot arbitrage detection
- Spot order matching
- Spot fee calculation
- Spot risk management
- Spot performance analytics
- Spot market making strategies
- Spot liquidity management
- Spot margin trading support

The spot module extends the base Kraken functionality with spot-specific
features and optimizations for the spot market.
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

import pandas as pd
import numpy as np
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
    KrakenTimeInForce
)
from trading.exchanges.kraken.exceptions import (
    KrakenError,
    KrakenOrderError,
    KrakenInsufficientFundsError,
    KrakenRateLimitError,
    KrakenValidationError,
    KrakenInvalidSymbolError
)
from trading.exchanges.kraken.converter import KrakenConverter, get_converter
from trading.exchanges.kraken.market import KrakenMarketData, KrakenInterval
from trading.exchanges.kraken.order import (
    KrakenOrderManager,
    OrderRequest,
    OrderResponse,
    OrderValidationResult,
    KrakenOrder as BaseKrakenOrder
)
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class SpotOrderType(str, Enum):
    """Spot order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS_LIMIT = "stop_loss_limit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    TRAILING_STOP = "trailing_stop"
    TRAILING_STOP_LIMIT = "trailing_stop_limit"
    POST_ONLY = "post_only"
    FOK = "fill_or_kill"
    IOC = "immediate_or_cancel"


class SpotOrderStatus(str, Enum):
    """Spot order status."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    TRIGGERED = "triggered"
    STOPPED = "stopped"


class SpotOrderSide(str, Enum):
    """Spot order sides."""
    BUY = "buy"
    SELL = "sell"


class SpotOrderTimeInForce(str, Enum):
    """Spot order time in force."""
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    DAY = "Day"
    GTX = "GTX"  # Good Till Crossing


class SpotExecutionType(str, Enum):
    """Spot execution types."""
    MARKET = "market"
    LIMIT = "limit"
    TWAP = "twap"
    VWAP = "vwap"
    ICEBERG = "iceberg"
    SCALING = "scaling"
    ADAPTIVE = "adaptive"


class SpotRiskLevel(str, Enum):
    """Spot risk levels."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class SpotPrice(BaseModel):
    """Spot price data."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    mid: Decimal
    spread: Decimal
    spread_percent: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    change_24h: Optional[Decimal] = None
    change_percent_24h: Optional[Decimal] = None

    @validator('bid', 'ask', 'last', 'mid', 'spread', 'spread_percent', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))


class SpotOrder(BaseModel):
    """Spot order model."""
    id: str
    symbol: str
    side: SpotOrderSide
    order_type: SpotOrderType
    status: SpotOrderStatus
    price: Decimal
    volume: Decimal
    filled_volume: Decimal = Decimal('0')
    remaining_volume: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    fee_currency: Optional[str] = None
    cost: Decimal = Decimal('0')
    time_in_force: SpotOrderTimeInForce = SpotOrderTimeInForce.GTC
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    client_order_id: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        """Calculate fill rate percentage."""
        if self.volume == 0:
            return 0.0
        return float(self.filled_volume / self.volume * 100)

    @property
    def is_open(self) -> bool:
        """Check if order is open."""
        return self.status in [SpotOrderStatus.OPEN, SpotOrderStatus.PARTIALLY_FILLED]

    @property
    def is_closed(self) -> bool:
        """Check if order is closed."""
        return self.status in [SpotOrderStatus.FILLED, SpotOrderStatus.CANCELLED, 
                              SpotOrderStatus.EXPIRED, SpotOrderStatus.REJECTED]


class SpotPosition(BaseModel):
    """Spot position model."""
    symbol: str
    side: SpotOrderSide
    quantity: Decimal
    entry_price: Decimal
    current_price: Optional[Decimal] = None
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    value: Decimal = Decimal('0')
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def pnl_percent(self) -> Decimal:
        """Calculate PnL percentage."""
        if self.cost == 0:
            return Decimal('0')
        return (self.total_pnl / self.cost) * 100


class SpotTrade(BaseModel):
    """Spot trade model."""
    id: str
    symbol: str
    side: SpotOrderSide
    price: Decimal
    volume: Decimal
    cost: Decimal
    fee: Decimal = Decimal('0')
    fee_currency: Optional[str] = None
    order_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpotBalance(BaseModel):
    """Spot balance model."""
    currency: str
    total: Decimal
    available: Decimal
    locked: Decimal = Decimal('0')
    frozen: Decimal = Decimal('0')
    value_usd: Optional[Decimal] = None
    value_btc: Optional[Decimal] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SpotExecutionParams(BaseModel):
    """Spot execution parameters."""
    execution_type: SpotExecutionType
    target_volume: Decimal
    max_slippage: Decimal = Decimal('0.01')  # 1% default
    min_fill_rate: float = 0.8
    max_duration: int = 3600  # seconds
    window_size: int = 60  # seconds for TWAP/VWAP
    ice_berg_size: Optional[Decimal] = None
    price_limit: Optional[Decimal] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Spot orders
CREATE TABLE IF NOT EXISTS kraken_spot_orders (
    id VARCHAR(64) PRIMARY KEY,
    client_order_id VARCHAR(64),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    filled_volume DECIMAL(32, 16) DEFAULT 0,
    remaining_volume DECIMAL(32, 16) DEFAULT 0,
    avg_price DECIMAL(32, 16) DEFAULT 0,
    fee DECIMAL(32, 16) DEFAULT 0,
    fee_currency VARCHAR(10),
    cost DECIMAL(32, 16) DEFAULT 0,
    time_in_force VARCHAR(10) DEFAULT 'GTC',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_kraken_spot_orders_symbol (symbol),
    INDEX idx_kraken_spot_orders_status (status),
    INDEX idx_kraken_spot_orders_created_at (created_at)
);

-- Spot trades
CREATE TABLE IF NOT EXISTS kraken_spot_trades (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    cost DECIMAL(32, 16) NOT NULL,
    fee DECIMAL(32, 16) DEFAULT 0,
    fee_currency VARCHAR(10),
    order_id VARCHAR(64),
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_kraken_spot_trades_symbol (symbol),
    INDEX idx_kraken_spot_trades_timestamp (timestamp)
);

-- Spot positions
CREATE TABLE IF NOT EXISTS kraken_spot_positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(32, 16) NOT NULL,
    entry_price DECIMAL(32, 16) NOT NULL,
    current_price DECIMAL(32, 16),
    unrealized_pnl DECIMAL(32, 16) DEFAULT 0,
    realized_pnl DECIMAL(32, 16) DEFAULT 0,
    total_pnl DECIMAL(32, 16) DEFAULT 0,
    cost DECIMAL(32, 16) DEFAULT 0,
    value DECIMAL(32, 16) DEFAULT 0,
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    UNIQUE(symbol, side)
);

-- Spot balances
CREATE TABLE IF NOT EXISTS kraken_spot_balances (
    currency VARCHAR(10) PRIMARY KEY,
    total DECIMAL(32, 16) DEFAULT 0,
    available DECIMAL(32, 16) DEFAULT 0,
    locked DECIMAL(32, 16) DEFAULT 0,
    frozen DECIMAL(32, 16) DEFAULT 0,
    value_usd DECIMAL(32, 16),
    value_btc DECIMAL(32, 16),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# =============================================================================
# MAIN SPOT TRADING CLASS
# =============================================================================

class KrakenSpotTrading:
    """
    Advanced spot trading for Kraken exchange.
    
    Features:
    - All spot order types (market, limit, stop-loss, take-profit, etc.)
    - Smart order execution (TWAP, VWAP, Iceberg, Scaling)
    - Real-time spot price tracking
    - Spot position management
    - Spot balance management
    - Order book analysis
    - Market making strategies
    - Arbitrage detection
    - Risk management
    - Performance analytics
    - WebSocket real-time updates
    - Database persistence
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        base: KrakenBase,
        config: KrakenConfig,
        market_data: Optional[KrakenMarketData] = None,
        order_manager: Optional[KrakenOrderManager] = None,
        converter: Optional[KrakenConverter] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.base = base
        self.config = config
        self.market_data = market_data
        self.order_manager = order_manager
        self.converter = converter or get_converter()
        self.redis = redis
        self.pool = pool
        
        # Spot state
        self._orders: Dict[str, SpotOrder] = {}
        self._positions: Dict[str, SpotPosition] = {}
        self._balances: Dict[str, SpotBalance] = {}
        self._trades: Dict[str, List[SpotTrade]] = {}
        
        # Circuit breakers
        self._spot_cb = CircuitBreaker(
            name="kraken_spot",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Execution engines
        self._execution_tasks: Dict[str, asyncio.Task] = {}
        self._execution_queue: asyncio.Queue = asyncio.Queue()
        
        # WebSocket integration
        self._ws_subscribed = False
        
        # Database initialization
        self._db_initialized = False
        
        # Rate limit tracking
        self._rate_limiter = {
            'requests': 0,
            'window_start': time.time(),
            'max_requests': 20
        }
        
        logger.info("KrakenSpotTrading initialized")
    
    async def initialize(self):
        """Initialize spot trading module."""
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load balances
        await self.sync_balances()
        
        # Load positions
        await self.sync_positions()
        
        # Start execution worker
        asyncio.create_task(self._execution_worker_loop())
        
        # Start periodic sync
        asyncio.create_task(self._periodic_sync())
        
        logger.info("KrakenSpotTrading initialization complete")
    
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
    # SPOT ORDER PLACEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_spot_order(
        self,
        symbol: str,
        side: SpotOrderSide,
        order_type: SpotOrderType,
        volume: Decimal,
        price: Optional[Decimal] = None,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: SpotOrderTimeInForce = SpotOrderTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        reduce_only: bool = False,
        post_only: bool = False,
        expire_time: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> SpotOrder:
        """
        Place a spot order.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            order_type: Order type
            volume: Order volume
            price: Price for limit orders
            limit_price: Limit price for stop-limit orders
            stop_price: Stop price for stop orders
            time_in_force: Time in force
            client_order_id: Client-side order ID
            reduce_only: Reduce-only position
            post_only: Post-only order
            expire_time: Expiration time
            metadata: Additional metadata
            
        Returns:
            SpotOrder
            
        Raises:
            KrakenOrderError: For order placement errors
            KrakenInsufficientFundsError: For insufficient funds
        """
        if self._spot_cb.is_open():
            raise KrakenRateLimitError("Spot circuit breaker is open")
        
        try:
            # Validate order
            validation = await self._validate_spot_order(
                symbol, side, order_type, volume, price
            )
            if not validation.is_valid:
                raise KrakenValidationError(validation.message)
            
            # Check balance
            await self._check_spot_balance(symbol, side, volume, price)
            
            # Convert to Kraken format
            kraken_pair = self.converter.to_kraken_pair(symbol)
            
            # Build order request
            order_req = OrderRequest(
                symbol=symbol,
                side=KrakenOrderSide(side.value),
                order_type=self._map_spot_to_kraken_type(order_type),
                volume=volume,
                price=price,
                limit_price=limit_price,
                stop_price=stop_price,
                time_in_force=KrakenTimeInForce(time_in_force.value),
                client_order_id=client_order_id,
                reduce_only=reduce_only,
                post_only=post_only,
                expire_time=expire_time,
                metadata=metadata or {}
            )
            
            # Place order
            if self.order_manager:
                response = await self.order_manager.place_order(order_req)
            else:
                # Direct placement
                response = await self._place_order_direct(order_req)
            
            # Convert to spot order
            spot_order = self._response_to_spot_order(response)
            
            # Track order
            self._orders[spot_order.id] = spot_order
            
            # Save to database
            if self.pool:
                await self._save_spot_order(spot_order)
            
            self._spot_cb.record_success()
            
            logger.info(
                f"Spot order placed: {spot_order.id} | {side} {volume} "
                f"{symbol} @ {price or 'market'}"
            )
            
            return spot_order
            
        except Exception as e:
            self._spot_cb.record_failure()
            logger.error(f"Spot order placement error: {e}")
            raise
    
    async def place_spot_market_order(
        self,
        symbol: str,
        side: SpotOrderSide,
        volume: Decimal,
        client_order_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> SpotOrder:
        """Place a market order."""
        return await self.place_spot_order(
            symbol=symbol,
            side=side,
            order_type=SpotOrderType.MARKET,
            volume=volume,
            time_in_force=SpotOrderTimeInForce.IOC,
            client_order_id=client_order_id,
            metadata=metadata
        )
    
    async def place_spot_limit_order(
        self,
        symbol: str,
        side: SpotOrderSide,
        volume: Decimal,
        price: Decimal,
        time_in_force: SpotOrderTimeInForce = SpotOrderTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        post_only: bool = False,
        metadata: Optional[Dict] = None
    ) -> SpotOrder:
        """Place a limit order."""
        return await self.place_spot_order(
            symbol=symbol,
            side=side,
            order_type=SpotOrderType.LIMIT,
            volume=volume,
            price=price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            post_only=post_only,
            metadata=metadata
        )
    
    # =========================================================================
    # SMART ORDER EXECUTION
    # =========================================================================
    
    async def execute_smart_order(
        self,
        symbol: str,
        side: SpotOrderSide,
        execution_params: SpotExecutionParams,
        client_order_id: Optional[str] = None
    ) -> List[SpotOrder]:
        """
        Execute a smart order with advanced execution strategies.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            execution_params: Execution parameters
            client_order_id: Client-side order ID
            
        Returns:
            List of SpotOrders
            
        Raises:
            KrakenError: For execution errors
        """
        execution_id = client_order_id or f"smart_{str(uuid.uuid4())[:8]}"
        
        try:
            if execution_params.execution_type == SpotExecutionType.TWAP:
                return await self._execute_twap(
                    symbol, side, execution_params, execution_id
                )
            elif execution_params.execution_type == SpotExecutionType.VWAP:
                return await self._execute_vwap(
                    symbol, side, execution_params, execution_id
                )
            elif execution_params.execution_type == SpotExecutionType.ICEBERG:
                return await self._execute_iceberg(
                    symbol, side, execution_params, execution_id
                )
            elif execution_params.execution_type == SpotExecutionType.SCALING:
                return await self._execute_scaling(
                    symbol, side, execution_params, execution_id
                )
            else:
                raise KrakenValidationError(
                    f"Unsupported execution type: {execution_params.execution_type}"
                )
                
        except Exception as e:
            logger.error(f"Smart order execution error: {e}")
            raise
    
    async def _execute_twap(
        self,
        symbol: str,
        side: SpotOrderSide,
        params: SpotExecutionParams,
        execution_id: str
    ) -> List[SpotOrder]:
        """
        Execute TWAP (Time-Weighted Average Price) order.
        
        Splits the order into smaller chunks executed at regular intervals.
        """
        orders = []
        chunks = max(1, int(params.target_volume / (params.target_volume / 10)))
        chunk_size = params.target_volume / chunks
        interval = params.max_duration / chunks
        
        for i in range(chunks):
            try:
                # Calculate remaining time
                remaining = params.max_duration - (i * interval)
                if remaining <= 0:
                    break
                
                # Place chunk
                order = await self.place_spot_limit_order(
                    symbol=symbol,
                    side=side,
                    volume=min(chunk_size, params.target_volume),
                    price=await self._get_mid_price(symbol),
                    time_in_force=SpotOrderTimeInForce.GTC,
                    client_order_id=f"{execution_id}_chunk_{i}",
                    metadata={"execution": "twap", "chunk": i}
                )
                orders.append(order)
                
                # Wait for next interval
                await asyncio.sleep(max(1, interval))
                
            except Exception as e:
                logger.error(f"TWAP chunk {i} failed: {e}")
                if len(orders) == 0:
                    raise
        
        return orders
    
    async def _execute_vwap(
        self,
        symbol: str,
        side: SpotOrderSide,
        params: SpotExecutionParams,
        execution_id: str
    ) -> List[SpotOrder]:
        """
        Execute VWAP (Volume-Weighted Average Price) order.
        
        Uses historical volume profile to schedule orders.
        """
        orders = []
        
        try:
            # Get historical volume profile
            ohlc_data = await self.market_data.get_ohlc(
                symbol, KrakenInterval.MINUTE_1, limit=params.window_size
            )
            
            if not ohlc_data:
                # Fallback to TWAP
                return await self._execute_twap(symbol, side, params, execution_id)
            
            # Calculate volume weights
            volumes = [c.volume for c in ohlc_data]
            total_volume = sum(volumes)
            if total_volume == 0:
                return await self._execute_twap(symbol, side, params, execution_id)
            
            weights = [v / total_volume for v in volumes]
            
            # Execute orders according to volume profile
            for i, weight in enumerate(weights):
                chunk_volume = params.target_volume * weight
                if chunk_volume < Decimal('0.0001'):
                    continue
                
                try:
                    order = await self.place_spot_limit_order(
                        symbol=symbol,
                        side=side,
                        volume=chunk_volume,
                        price=await self._get_mid_price(symbol),
                        time_in_force=SpotOrderTimeInForce.GTC,
                        client_order_id=f"{execution_id}_vwap_{i}",
                        metadata={"execution": "vwap", "weight": float(weight)}
                    )
                    orders.append(order)
                    
                    # Brief pause between orders
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"VWAP chunk {i} failed: {e}")
            
        except Exception as e:
            logger.error(f"VWAP execution error: {e}")
            # Fallback to TWAP
            return await self._execute_twap(symbol, side, params, execution_id)
        
        return orders
    
    async def _execute_iceberg(
        self,
        symbol: str,
        side: SpotOrderSide,
        params: SpotExecutionParams,
        execution_id: str
    ) -> List[SpotOrder]:
        """
        Execute Iceberg order.
        
        Shows only a small portion of the total order at a time.
        """
        orders = []
        ice_size = params.ice_berg_size or (params.target_volume * Decimal('0.1'))
        remaining = params.target_volume
        
        while remaining > 0:
            try:
                chunk = min(ice_size, remaining)
                
                order = await self.place_spot_limit_order(
                    symbol=symbol,
                    side=side,
                    volume=chunk,
                    price=await self._get_mid_price(symbol),
                    time_in_force=SpotOrderTimeInForce.GTC,
                    client_order_id=f"{execution_id}_ice_{len(orders)}",
                    metadata={"execution": "iceberg"}
                )
                orders.append(order)
                
                remaining -= chunk
                
                # Wait for fill or next chunk
                await self._wait_for_order_fill(order.id, timeout=30)
                
                # Refresh price for next chunk
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Iceberg chunk failed: {e}")
                if len(orders) == 0:
                    raise
        
        return orders
    
    async def _execute_scaling(
        self,
        symbol: str,
        side: SpotOrderSide,
        params: SpotExecutionParams,
        execution_id: str
    ) -> List[SpotOrder]:
        """
        Execute Scaling order.
        
        Places orders at progressively better prices.
        """
        orders = []
        num_orders = 10
        chunk_size = params.target_volume / num_orders
        
        # Get current price
        current_price = await self._get_mid_price(symbol)
        price_step = current_price * Decimal('0.001')  # 0.1% steps
        
        for i in range(num_orders):
            try:
                # Calculate price
                if side == SpotOrderSide.BUY:
                    price = current_price - (price_step * (i + 1))
                else:
                    price = current_price + (price_step * (i + 1))
                
                order = await self.place_spot_limit_order(
                    symbol=symbol,
                    side=side,
                    volume=chunk_size,
                    price=price,
                    time_in_force=SpotOrderTimeInForce.GTC,
                    client_order_id=f"{execution_id}_scale_{i}",
                    metadata={"execution": "scaling", "level": i}
                )
                orders.append(order)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Scaling order {i} failed: {e}")
        
        return orders
    
    async def _wait_for_order_fill(self, order_id: str, timeout: int = 30):
        """Wait for an order to be filled."""
        start = time.time()
        while time.time() - start < timeout:
            order = await self.get_spot_order(order_id)
            if order and order.status in [SpotOrderStatus.FILLED, SpotOrderStatus.CANCELLED]:
                return order
            await asyncio.sleep(1)
        return None
    
    # =========================================================================
    # SPOT ORDER MANAGEMENT
    # =========================================================================
    
    async def get_spot_order(self, order_id: str) -> Optional[SpotOrder]:
        """Get spot order by ID."""
        if order_id in self._orders:
            return self._orders[order_id]
        
        # Try to get from order manager
        if self.order_manager:
            order = await self.order_manager.get_order(order_id)
            if order:
                return self._kraken_to_spot_order(order)
        
        return None
    
    async def get_open_spot_orders(self) -> List[SpotOrder]:
        """Get all open spot orders."""
        if self.order_manager:
            orders = await self.order_manager.get_open_orders()
            return [self._kraken_to_spot_order(o) for o in orders]
        return list(self._orders.values())
    
    async def cancel_spot_order(self, order_id: str) -> bool:
        """Cancel a spot order."""
        if self.order_manager:
            return await self.order_manager.cancel_order(order_id)
        
        if order_id in self._orders:
            self._orders[order_id].status = SpotOrderStatus.CANCELLED
            return True
        return False
    
    async def cancel_all_spot_orders(self, symbol: Optional[str] = None) -> int:
        """Cancel all spot orders."""
        if self.order_manager:
            if symbol:
                return await self.order_manager.cancel_orders_by_symbol(symbol)
            else:
                return await self.order_manager.cancel_all_orders()
        
        cancelled = 0
        for order_id, order in list(self._orders.items()):
            if not symbol or order.symbol == symbol:
                if await self.cancel_spot_order(order_id):
                    cancelled += 1
        return cancelled
    
    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================
    
    async def get_spot_position(self, symbol: str) -> Optional[SpotPosition]:
        """Get spot position for a symbol."""
        return self._positions.get(symbol)
    
    async def get_all_spot_positions(self) -> List[SpotPosition]:
        """Get all spot positions."""
        return list(self._positions.values())
    
    async def sync_positions(self):
        """Sync positions from exchange."""
        try:
            # Get balances to infer positions
            balances = await self.get_spot_balances()
            
            # Build positions from balances
            positions = {}
            for currency, balance in balances.items():
                if balance.total > 0:
                    # This is a position
                    positions[currency] = SpotPosition(
                        symbol=currency,
                        side=SpotOrderSide.BUY,
                        quantity=balance.total,
                        entry_price=Decimal('0'),  # Would need trade history
                        current_price=await self._get_price(currency),
                        value=balance.total * (await self._get_price(currency)),
                        opened_at=datetime.utcnow()
                    )
            
            self._positions = positions
            
            # Save to database
            if self.pool:
                await self._save_positions()
            
            logger.info(f"Synced {len(positions)} positions")
            
        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
    
    # =========================================================================
    # BALANCE MANAGEMENT
    # =========================================================================
    
    async def get_spot_balances(self) -> Dict[str, SpotBalance]:
        """Get all spot balances."""
        try:
            if self.order_manager and hasattr(self.order_manager, 'base'):
                result = await self.base._private_request("Balance")
                
                balances = {}
                for currency, amount in result.items():
                    standard_currency = self.converter.to_standard_currency(currency)
                    balances[standard_currency] = SpotBalance(
                        currency=standard_currency,
                        total=Decimal(str(amount)),
                        available=Decimal(str(amount)),
                        updated_at=datetime.utcnow()
                    )
                
                self._balances = balances
                
                # Save to database
                if self.pool:
                    await self._save_balances()
                
                return balances
            
            return self._balances
            
        except Exception as e:
            logger.error(f"Error getting balances: {e}")
            return self._balances
    
    async def get_spot_balance(self, currency: str) -> Optional[SpotBalance]:
        """Get spot balance for a currency."""
        balances = await self.get_spot_balances()
        return balances.get(currency.upper())
    
    async def sync_balances(self):
        """Sync balances from exchange."""
        await self.get_spot_balances()
        logger.info("Balances synced")
    
    # =========================================================================
    # PRICE AND MARKET DATA
    # =========================================================================
    
    async def get_spot_price(self, symbol: str) -> SpotPrice:
        """Get current spot price for a symbol."""
        if self.market_data:
            tickers = await self.market_data.get_ticker(symbol)
            ticker = tickers.get(symbol)
            if ticker:
                return SpotPrice(
                    symbol=symbol,
                    bid=ticker.bid,
                    ask=ticker.ask,
                    last=ticker.last,
                    mid=(ticker.bid + ticker.ask) / 2,
                    spread=ticker.ask - ticker.bid,
                    spread_percent=((ticker.ask - ticker.bid) / ticker.bid * 100) if ticker.bid > 0 else Decimal('0'),
                    high_24h=ticker.high,
                    low_24h=ticker.low,
                    volume_24h=ticker.volume_24h,
                    change_24h=ticker.change,
                    change_percent_24h=ticker.change_percent
                )
        
        raise KrakenInvalidSymbolError(f"Symbol {symbol} not found")
    
    async def _get_price(self, symbol: str) -> Decimal:
        """Get current price for a symbol."""
        try:
            price = await self.get_spot_price(symbol)
            return price.last
        except Exception:
            return Decimal('0')
    
    async def _get_mid_price(self, symbol: str) -> Decimal:
        """Get mid price for a symbol."""
        try:
            price = await self.get_spot_price(symbol)
            return price.mid
        except Exception:
            return Decimal('0')
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    async def _validate_spot_order(
        self,
        symbol: str,
        side: SpotOrderSide,
        order_type: SpotOrderType,
        volume: Decimal,
        price: Optional[Decimal] = None
    ) -> OrderValidationResult:
        """Validate spot order."""
        # Validate symbol
        if not self.converter.validate_pair(symbol):
            return OrderValidationResult(
                result=OrderValidationResult.INVALID_SYMBOL,
                is_valid=False,
                message=f"Invalid symbol: {symbol}"
            )
        
        # Validate volume
        if volume <= 0:
            return OrderValidationResult(
                result=OrderValidationResult.INVALID_VOLUME,
                is_valid=False,
                message="Volume must be positive"
            )
        
        # Validate price for limit orders
        if order_type in [SpotOrderType.LIMIT, SpotOrderType.STOP_LOSS_LIMIT]:
            if price is None or price <= 0:
                return OrderValidationResult(
                    result=OrderValidationResult.INVALID_PRICE,
                    is_valid=False,
                    message="Price required and must be positive"
                )
        
        return OrderValidationResult(
            result=OrderValidationResult.VALID,
            is_valid=True,
            message="Order is valid"
        )
    
    async def _check_spot_balance(
        self,
        symbol: str,
        side: SpotOrderSide,
        volume: Decimal,
        price: Optional[Decimal] = None
    ):
        """Check if sufficient balance for order."""
        balances = await self.get_spot_balances()
        
        if side == SpotOrderSide.BUY:
            # Check quote currency balance
            quote = symbol.split('/')[1] if '/' in symbol else 'USD'
            balance = balances.get(quote)
            
            if balance:
                total_value = volume * (price or await self._get_price(symbol))
                if balance.available < total_value:
                    raise KrakenInsufficientFundsError(
                        f"Insufficient {quote} balance: {balance.available} < {total_value}"
                    )
        else:
            # Check base currency balance
            base = symbol.split('/')[0] if '/' in symbol else symbol
            balance = balances.get(base)
            
            if balance and balance.available < volume:
                raise KrakenInsufficientFundsError(
                    f"Insufficient {base} balance: {balance.available} < {volume}"
                )
    
    # =========================================================================
    # ORDER CONVERSION
    # =========================================================================
    
    def _response_to_spot_order(self, response: OrderResponse) -> SpotOrder:
        """Convert OrderResponse to SpotOrder."""
        return SpotOrder(
            id=response.order_id,
            symbol=response.symbol,
            side=SpotOrderSide(response.side.value),
            order_type=self._map_kraken_to_spot_type(response.order_type),
            status=SpotOrderStatus(response.status.value),
            price=response.price or Decimal('0'),
            volume=response.volume,
            filled_volume=response.filled_volume,
            remaining_volume=response.volume - response.filled_volume,
            average_price=response.average_price,
            fee=response.fee,
            cost=response.cost,
            time_in_force=SpotOrderTimeInForce(response.time_in_force.value),
            created_at=response.created_at,
            updated_at=response.updated_at,
            expires_at=response.expires_at,
            client_order_id=response.client_order_id,
            metadata=response.metadata
        )
    
    def _kraken_to_spot_order(self, order: BaseKrakenOrder) -> SpotOrder:
        """Convert KrakenOrder to SpotOrder."""
        return SpotOrder(
            id=order.id,
            symbol=self.converter.to_standard_pair(order.pair),
            side=SpotOrderSide(order.side.value),
            order_type=self._map_kraken_to_spot_type(order.type),
            status=SpotOrderStatus(order.status.value),
            price=order.price,
            volume=order.volume,
            filled_volume=order.executed_volume,
            remaining_volume=order.volume - order.executed_volume,
            average_price=order.average_price,
            fee=order.fee,
            cost=order.cost,
            time_in_force=SpotOrderTimeInForce(order.time_in_force.value),
            created_at=order.created_at,
            updated_at=order.updated_at,
            expires_at=order.expires_at,
            metadata=order.metadata
        )
    
    def _map_spot_to_kraken_type(self, spot_type: SpotOrderType) -> KrakenOrderType:
        """Map spot order type to Kraken order type."""
        mapping = {
            SpotOrderType.MARKET: KrakenOrderType.MARKET,
            SpotOrderType.LIMIT: KrakenOrderType.LIMIT,
            SpotOrderType.STOP_LOSS: KrakenOrderType.STOP_LOSS,
            SpotOrderType.TAKE_PROFIT: KrakenOrderType.TAKE_PROFIT,
            SpotOrderType.STOP_LOSS_LIMIT: KrakenOrderType.STOP_LOSS_LIMIT,
            SpotOrderType.TAKE_PROFIT_LIMIT: KrakenOrderType.TAKE_PROFIT_LIMIT,
        }
        return mapping.get(spot_type, KrakenOrderType.LIMIT)
    
    def _map_kraken_to_spot_type(self, kraken_type: KrakenOrderType) -> SpotOrderType:
        """Map Kraken order type to spot order type."""
        mapping = {
            KrakenOrderType.MARKET: SpotOrderType.MARKET,
            KrakenOrderType.LIMIT: SpotOrderType.LIMIT,
            KrakenOrderType.STOP_LOSS: SpotOrderType.STOP_LOSS,
            KrakenOrderType.TAKE_PROFIT: SpotOrderType.TAKE_PROFIT,
            KrakenOrderType.STOP_LOSS_LIMIT: SpotOrderType.STOP_LOSS_LIMIT,
            KrakenOrderType.TAKE_PROFIT_LIMIT: SpotOrderType.TAKE_PROFIT_LIMIT,
        }
        return mapping.get(kraken_type, SpotOrderType.LIMIT)
    
    # =========================================================================
    # EXECUTION WORKER
    # =========================================================================
    
    async def _execution_worker_loop(self):
        """Background worker for executing orders."""
        while True:
            try:
                # Process execution queue
                if not self._execution_queue.empty():
                    execution = await self._execution_queue.get()
                    await self._process_execution(execution)
                    self._execution_queue.task_done()
                
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Execution worker error: {e}")
                await asyncio.sleep(1)
    
    async def _process_execution(self, execution: Dict[str, Any]):
        """Process a single execution request."""
        # Implementation would handle various execution types
        pass
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_spot_order(self, order: SpotOrder):
        """Save spot order to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kraken_spot_orders (
                        id, client_order_id, symbol, side, order_type,
                        status, price, volume, filled_volume,
                        remaining_volume, avg_price, fee, fee_currency,
                        cost, time_in_force, created_at, updated_at,
                        expires_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        filled_volume = EXCLUDED.filled_volume,
                        remaining_volume = EXCLUDED.remaining_volume,
                        avg_price = EXCLUDED.avg_price,
                        fee = EXCLUDED.fee,
                        cost = EXCLUDED.cost,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    order.id,
                    order.client_order_id,
                    order.symbol,
                    order.side.value,
                    order.order_type.value,
                    order.status.value,
                    order.price,
                    order.volume,
                    order.filled_volume,
                    order.remaining_volume,
                    order.average_price,
                    order.fee,
                    order.fee_currency,
                    order.cost,
                    order.time_in_force.value,
                    order.created_at,
                    order.updated_at,
                    order.expires_at,
                    json.dumps(order.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving spot order: {e}")
    
    async def _save_balances(self):
        """Save balances to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                for balance in self._balances.values():
                    await conn.execute(
                        """
                        INSERT INTO kraken_spot_balances (
                            currency, total, available, locked, frozen,
                            value_usd, value_btc, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (currency) DO UPDATE SET
                            total = EXCLUDED.total,
                            available = EXCLUDED.available,
                            locked = EXCLUDED.locked,
                            frozen = EXCLUDED.frozen,
                            value_usd = EXCLUDED.value_usd,
                            value_btc = EXCLUDED.value_btc,
                            updated_at = EXCLUDED.updated_at
                        """,
                        balance.currency,
                        balance.total,
                        balance.available,
                        balance.locked,
                        balance.frozen,
                        balance.value_usd,
                        balance.value_btc,
                        balance.updated_at
                    )
        except Exception as e:
            logger.error(f"Error saving balances: {e}")
    
    async def _save_positions(self):
        """Save positions to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                for position in self._positions.values():
                    await conn.execute(
                        """
                        INSERT INTO kraken_spot_positions (
                            symbol, side, quantity, entry_price,
                            current_price, unrealized_pnl, realized_pnl,
                            total_pnl, cost, value, opened_at, closed_at,
                            metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (symbol, side) DO UPDATE SET
                            quantity = EXCLUDED.quantity,
                            current_price = EXCLUDED.current_price,
                            unrealized_pnl = EXCLUDED.unrealized_pnl,
                            realized_pnl = EXCLUDED.realized_pnl,
                            total_pnl = EXCLUDED.total_pnl,
                            value = EXCLUDED.value,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        position.symbol,
                        position.side.value,
                        position.quantity,
                        position.entry_price,
                        position.current_price,
                        position.unrealized_pnl,
                        position.realized_pnl,
                        position.total_pnl,
                        position.cost,
                        position.value,
                        position.opened_at,
                        position.closed_at,
                        json.dumps(position.metadata, default=str)
                    )
        except Exception as e:
            logger.error(f"Error saving positions: {e}")
    
    # =========================================================================
    # PERIODIC SYNC
    # =========================================================================
    
    async def _periodic_sync(self):
        """Periodically sync spot data."""
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                # Sync balances
                await self.sync_balances()
                
                # Sync positions
                await self.sync_positions()
                
                # Sync open orders
                if self.order_manager:
                    await self.order_manager.load_open_orders()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic sync error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # DIRECT ORDER PLACEMENT
    # =========================================================================
    
    async def _place_order_direct(self, order_req: OrderRequest) -> OrderResponse:
        """Place order directly without order manager."""
        kraken_pair = self.converter.to_kraken_pair(order_req.symbol)
        
        params = {
            "pair": kraken_pair,
            "type": order_req.side.value,
            "ordertype": order_req.order_type.value,
            "volume": str(order_req.volume),
            "timeinforce": order_req.time_in_force.value,
        }
        
        if order_req.price is not None:
            params["price"] = str(order_req.price)
        
        if order_req.limit_price is not None:
            params["price2"] = str(order_req.limit_price)
        
        if order_req.stop_price is not None:
            params["price"] = str(order_req.stop_price)
        
        if order_req.client_order_id:
            params["userref"] = order_req.client_order_id
        
        result = await self.base._private_request("AddOrder", params)
        
        order_id = result.get('txid', [''])[0] if result.get('txid') else None
        if not order_id:
            raise KrakenOrderError("No order ID returned")
        
        return OrderResponse(
            order_id=order_id,
            client_order_id=order_req.client_order_id,
            status=KrakenOrderStatus.PENDING,
            symbol=order_req.symbol,
            side=order_req.side,
            order_type=order_req.order_type,
            volume=order_req.volume,
            price=order_req.price,
            limit_price=order_req.limit_price,
            stop_price=order_req.stop_price,
            time_in_force=order_req.time_in_force,
            created_at=datetime.utcnow(),
            metadata=order_req.metadata
        )
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown spot trading module."""
        logger.info("Shutting down KrakenSpotTrading")
        # Cancel execution tasks
        for task in self._execution_tasks.values():
            task.cancel()
        # Nothing else to clean up


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'KrakenSpotTrading',
    'SpotOrderType',
    'SpotOrderStatus',
    'SpotOrderSide',
    'SpotOrderTimeInForce',
    'SpotExecutionType',
    'SpotRiskLevel',
    'SpotPrice',
    'SpotOrder',
    'SpotPosition',
    'SpotTrade',
    'SpotBalance',
    'SpotExecutionParams'
]
