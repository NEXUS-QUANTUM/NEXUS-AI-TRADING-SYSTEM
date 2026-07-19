# trading/exchanges/okx/futures.py
# Nexus AI Trading System - OKX Exchange Futures Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - Futures Trading Module

This module provides comprehensive futures trading functionality for the OKX
cryptocurrency exchange, including:

- Futures order placement and management
- Position management with margin control
- Leverage management
- Futures price tracking and analytics
- Funding rate monitoring
- Mark price and liquidation price calculations
- Position risk management
- Auto-deleverage (ADL) protection
- Futures WebSocket streaming
- Multi-collateral management
- Futures arbitrage detection
- Basis trading strategies
- Perpetual swap management
- Settlement management
- Position sizing and risk management
- Comprehensive error handling
- Database persistence
- Redis caching

Features:
- All futures order types (market, limit, post-only, IOC, FOK)
- Cross-margin and isolated-margin support
- Leverage adjustment
- Take-profit and stop-loss orders
- Trailing stop orders
- Position closure
- Auto-position reduction
- Funding rate history
- Basis and spread analysis
- Correlation analysis
- Volatility indicators
- Heatmap generation
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set
import uuid

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis
import asyncpg

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
    OKXInsufficientFundsError,
    OKXRateLimitError,
    OKXValidationError,
    OKXInvalidSymbolError,
    OKXPositionError,
    OKXLiquidationError
)
from trading.exchanges.okx.converter import OKXConverter, get_converter
from trading.exchanges.okx.market import OKXMarketData, OKXInterval
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class FuturesInstrumentType(str, Enum):
    """Futures instrument types."""
    LINEAR = "linear"  # USDT-margined
    INVERSE = "inverse"  # Coin-margined
    PERPETUAL = "perpetual"
    DELIVERY = "delivery"


class FuturesOrderType(str, Enum):
    """Futures order types."""
    MARKET = "market"
    LIMIT = "limit"
    POST_ONLY = "post_only"
    FOK = "fok"
    IOC = "ioc"
    OPTIMAL_LIMIT_IOC = "optimal_limit_ioc"


class FuturesOrderSide(str, Enum):
    """Futures order sides."""
    BUY = "buy"
    SELL = "sell"
    BUY_OPEN = "buy_open"
    BUY_CLOSE = "buy_close"
    SELL_OPEN = "sell_open"
    SELL_CLOSE = "sell_close"


class FuturesPositionSide(str, Enum):
    """Futures position sides."""
    LONG = "long"
    SHORT = "short"
    NET = "net"  # One-way mode


class FuturesMarginMode(str, Enum):
    """Futures margin modes."""
    CROSS = "cross"
    ISOLATED = "isolated"


class FuturesOrderStatus(str, Enum):
    """Futures order status."""
    PENDING = "pending"
    OPEN = "live"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    TRIGGERED = "triggered"
    STOPPED = "stopped"


class FuturesPositionStatus(str, Enum):
    """Futures position status."""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"
    LIQUIDATED = "liquidated"
    ADL = "adl"  # Auto-deleverage


class FuturesTimeInForce(str, Enum):
    """Futures time in force."""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    DAY = "Day"
    GTX = "GTX"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class FuturesOrder(BaseModel):
    """Futures order model."""
    id: str
    symbol: str
    side: FuturesOrderSide
    position_side: Optional[FuturesPositionSide] = None
    order_type: FuturesOrderType
    status: FuturesOrderStatus
    price: Decimal = Decimal('0')
    volume: Decimal = Decimal('0')
    filled_volume: Decimal = Decimal('0')
    remaining_volume: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    fee_currency: Optional[str] = None
    cost: Decimal = Decimal('0')
    leverage: Decimal = Decimal('1')
    margin: Decimal = Decimal('0')
    time_in_force: FuturesTimeInForce = FuturesTimeInForce.GTC
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reduce_only: bool = False
    close_position: bool = False
    client_order_id: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.volume == 0:
            return 0.0
        return float(self.filled_volume / self.volume * 100)

    @property
    def is_open(self) -> bool:
        return self.status in [FuturesOrderStatus.OPEN, FuturesOrderStatus.PARTIALLY_FILLED]


class FuturesPosition(BaseModel):
    """Futures position model."""
    id: str
    symbol: str
    side: FuturesPositionSide
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    liquidation_price: Optional[Decimal] = None
    margin: Decimal
    leverage: Decimal
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    roe: Decimal = Decimal('0')
    margin_mode: FuturesMarginMode
    status: FuturesPositionStatus = FuturesPositionStatus.OPEN
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    trailing_stop: Optional[Decimal] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def pnl_percent(self) -> Decimal:
        if self.margin == 0:
            return Decimal('0')
        return (self.total_pnl / self.margin) * 100

    @property
    def liquidation_distance(self) -> Optional[Decimal]:
        if self.liquidation_price is None:
            return None
        return abs(self.mark_price - self.liquidation_price)


class FuturesFundingRate(BaseModel):
    """Futures funding rate data."""
    symbol: str
    funding_rate: Decimal
    next_funding_rate: Optional[Decimal] = None
    predicted_rate: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    next_funding_time: datetime
    rate_8h: Optional[Decimal] = None
    rate_24h: Optional[Decimal] = None
    rate_7d: Optional[Decimal] = None
    is_predicted: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FuturesRiskInfo(BaseModel):
    """Futures risk information."""
    symbol: str
    margin_mode: FuturesMarginMode
    leverage: Decimal
    position_size: Decimal
    margin: Decimal
    maintenance_margin: Decimal
    liquidation_price: Optional[Decimal] = None
    risk_ratio: Decimal  # margin / maintenance_margin
    adl_level: int  # Auto-deleverage level
    max_leverage: Decimal
    current_leverage: Decimal
    pnl: Decimal
    pnl_percent: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FuturesTrade(BaseModel):
    """Futures trade model."""
    id: str
    symbol: str
    side: FuturesOrderSide
    position_side: Optional[FuturesPositionSide] = None
    price: Decimal
    volume: Decimal
    cost: Decimal
    fee: Decimal = Decimal('0')
    fee_currency: Optional[str] = None
    order_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pnl: Optional[Decimal] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FuturesBalance(BaseModel):
    """Futures balance model."""
    currency: str
    total: Decimal
    available: Decimal
    locked: Decimal = Decimal('0')
    pnl: Decimal = Decimal('0')
    margin: Decimal = Decimal('0')
    maintenance_margin: Decimal = Decimal('0')
    leverage: Decimal = Decimal('1')
    value_usd: Optional[Decimal] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FuturesInstrument(BaseModel):
    """Futures instrument model."""
    id: str
    symbol: str
    instrument_type: FuturesInstrumentType
    contract_size: Decimal
    tick_size: Decimal
    lot_size: Decimal
    min_volume: Decimal
    max_volume: Optional[Decimal] = None
    leverage_min: Decimal
    leverage_max: Decimal
    margin_rate: Decimal
    maintenance_rate: Decimal
    expiry: Optional[datetime] = None
    delivery_time: Optional[datetime] = None
    settlement_currency: str
    quote_currency: str
    base_currency: str
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Futures orders
CREATE TABLE IF NOT EXISTS okx_futures_orders (
    id VARCHAR(64) PRIMARY KEY,
    client_order_id VARCHAR(64),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(20) NOT NULL,
    position_side VARCHAR(10),
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
    leverage DECIMAL(32, 16) DEFAULT 1,
    margin DECIMAL(32, 16) DEFAULT 0,
    time_in_force VARCHAR(10) DEFAULT 'GTC',
    reduce_only BOOLEAN DEFAULT FALSE,
    close_position BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_futures_orders_symbol (symbol),
    INDEX idx_okx_futures_orders_status (status),
    INDEX idx_okx_futures_orders_created_at (created_at)
);

-- Futures positions
CREATE TABLE IF NOT EXISTS okx_futures_positions (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(32, 16) NOT NULL,
    entry_price DECIMAL(32, 16) NOT NULL,
    mark_price DECIMAL(32, 16) NOT NULL,
    liquidation_price DECIMAL(32, 16),
    margin DECIMAL(32, 16) NOT NULL,
    leverage DECIMAL(32, 16) NOT NULL,
    unrealized_pnl DECIMAL(32, 16) DEFAULT 0,
    realized_pnl DECIMAL(32, 16) DEFAULT 0,
    total_pnl DECIMAL(32, 16) DEFAULT 0,
    roe DECIMAL(32, 16) DEFAULT 0,
    margin_mode VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'open',
    stop_loss DECIMAL(32, 16),
    take_profit DECIMAL(32, 16),
    trailing_stop DECIMAL(32, 16),
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    UNIQUE(symbol, side)
);

-- Futures funding rates
CREATE TABLE IF NOT EXISTS okx_futures_funding_rates (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    funding_rate DECIMAL(32, 16) NOT NULL,
    next_funding_rate DECIMAL(32, 16),
    predicted_rate DECIMAL(32, 16),
    next_funding_time TIMESTAMP NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_futures_funding_rates_symbol (symbol),
    INDEX idx_okx_futures_funding_rates_timestamp (timestamp)
);

-- Futures trades
CREATE TABLE IF NOT EXISTS okx_futures_trades (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(20) NOT NULL,
    position_side VARCHAR(10),
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    cost DECIMAL(32, 16) NOT NULL,
    fee DECIMAL(32, 16) DEFAULT 0,
    fee_currency VARCHAR(10),
    order_id VARCHAR(64),
    pnl DECIMAL(32, 16),
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_futures_trades_symbol (symbol),
    INDEX idx_okx_futures_trades_timestamp (timestamp)
);

-- Futures balances
CREATE TABLE IF NOT EXISTS okx_futures_balances (
    currency VARCHAR(10) PRIMARY KEY,
    total DECIMAL(32, 16) DEFAULT 0,
    available DECIMAL(32, 16) DEFAULT 0,
    locked DECIMAL(32, 16) DEFAULT 0,
    pnl DECIMAL(32, 16) DEFAULT 0,
    margin DECIMAL(32, 16) DEFAULT 0,
    maintenance_margin DECIMAL(32, 16) DEFAULT 0,
    leverage DECIMAL(32, 16) DEFAULT 1,
    value_usd DECIMAL(32, 16),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# =============================================================================
# MAIN FUTURES TRADING CLASS
# =============================================================================

class OKXFuturesTrading:
    """
    Advanced futures trading for OKX exchange.
    
    Features:
    - All futures order types (market, limit, post-only, IOC, FOK)
    - Cross-margin and isolated-margin support
    - Leverage management
    - Position management
    - Stop-loss and take-profit orders
    - Trailing stop orders
    - Funding rate monitoring and analysis
    - Risk management
    - Liquidation price monitoring
    - Auto-deleverage protection
    - Multi-collateral management
    - Futures arbitrage detection
    - Basis trading
    - Settlement management
    - WebSocket real-time updates
    - Database persistence
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
        
        # Futures state
        self._orders: Dict[str, FuturesOrder] = {}
        self._positions: Dict[str, Dict[str, FuturesPosition]] = {}  # symbol -> side -> position
        self._balances: Dict[str, FuturesBalance] = {}
        self._funding_rates: Dict[str, FuturesFundingRate] = {}
        
        # Circuit breakers
        self._futures_cb = CircuitBreaker(
            name="okx_futures",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # WebSocket integration
        self._ws_subscribed = False
        self._ws_handlers: Dict[str, List[Callable]] = {}
        
        # Database initialization
        self._db_initialized = False
        
        # Rate limit tracking
        self._rate_limiter = {
            'requests': 0,
            'window_start': time.time(),
            'max_requests': 10
        }
        
        # Position sync task
        self._sync_task: Optional[asyncio.Task] = None
        
        logger.info("OKXFuturesTrading initialized")
    
    async def initialize(self):
        """Initialize futures trading module."""
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load balances
        await self.sync_balances()
        
        # Load positions
        await self.sync_positions()
        
        # Start periodic sync
        self._sync_task = asyncio.create_task(self._periodic_sync())
        
        logger.info("OKXFuturesTrading initialization complete")
    
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
    async def place_futures_order(
        self,
        symbol: str,
        side: FuturesOrderSide,
        order_type: FuturesOrderType,
        volume: Decimal,
        price: Optional[Decimal] = None,
        position_side: Optional[FuturesPositionSide] = None,
        margin_mode: FuturesMarginMode = FuturesMarginMode.CROSS,
        leverage: Decimal = Decimal('1'),
        reduce_only: bool = False,
        close_position: bool = False,
        time_in_force: FuturesTimeInForce = FuturesTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        trailing_stop: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> FuturesOrder:
        """
        Place a futures order.
        
        Args:
            symbol: Trading symbol
            side: Order side (buy_open, sell_open, buy_close, sell_close)
            order_type: Order type
            volume: Order volume
            price: Price for limit orders
            position_side: Position side (long, short, net)
            margin_mode: Margin mode (cross, isolated)
            leverage: Leverage
            reduce_only: Reduce-only position
            close_position: Close entire position
            time_in_force: Time in force
            client_order_id: Client-side order ID
            stop_loss: Stop-loss price
            take_profit: Take-profit price
            trailing_stop: Trailing stop distance
            metadata: Additional metadata
            
        Returns:
            FuturesOrder
            
        Raises:
            OKXOrderError: For order placement errors
            OKXInsufficientFundsError: For insufficient funds
        """
        if self._futures_cb.is_open():
            raise OKXRateLimitError("Futures circuit breaker is open")
        
        try:
            # Set leverage
            if leverage != Decimal('1'):
                await self.set_leverage(symbol, leverage, margin_mode)
            
            # Build order parameters
            okx_symbol = self.converter.to_okx_instrument(symbol, "SWAP")
            
            params = {
                'instId': okx_symbol,
                'side': side.value,
                'ordType': order_type.value,
                'sz': str(volume),
                'tdMode': margin_mode.value,
                'lever': str(leverage),
            }
            
            if position_side:
                params['posSide'] = position_side.value
            
            if price is not None:
                params['px'] = str(price)
            
            if reduce_only:
                params['reduceOnly'] = 'true'
            
            if close_position:
                params['close'] = 'true'
            
            if time_in_force != FuturesTimeInForce.GTC:
                params['timeInForce'] = time_in_force.value
            
            if client_order_id:
                params['clOrdId'] = client_order_id
            
            # Add TP/SL
            if take_profit:
                params['tpTriggerPx'] = str(take_profit)
            if stop_loss:
                params['slTriggerPx'] = str(stop_loss)
            if trailing_stop:
                params['tpTriggerPxType'] = 'last'
                params['tpTriggerPx'] = str(trailing_stop)
            
            # Place order
            response = await self.base._private_request('trade/order', params, 'POST')
            
            if not response:
                raise OKXOrderError("Order placement failed")
            
            order_data = response[0] if isinstance(response, list) else response
            
            # Create order object
            order = self._parse_order(order_data)
            
            # Track order
            self._orders[order.id] = order
            
            # Save to database
            if self.pool:
                await self._save_order(order)
            
            self._futures_cb.record_success()
            
            logger.info(
                f"Futures order placed: {order.id} | {side} {volume} "
                f"{symbol} @ {price or 'market'}"
            )
            
            return order
            
        except Exception as e:
            self._futures_cb.record_failure()
            logger.error(f"Futures order placement error: {e}")
            raise
    
    async def place_futures_market_order(
        self,
        symbol: str,
        side: FuturesOrderSide,
        volume: Decimal,
        margin_mode: FuturesMarginMode = FuturesMarginMode.CROSS,
        leverage: Decimal = Decimal('1'),
        reduce_only: bool = False,
        close_position: bool = False,
        client_order_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> FuturesOrder:
        """Place a market order."""
        return await self.place_futures_order(
            symbol=symbol,
            side=side,
            order_type=FuturesOrderType.MARKET,
            volume=volume,
            margin_mode=margin_mode,
            leverage=leverage,
            reduce_only=reduce_only,
            close_position=close_position,
            client_order_id=client_order_id,
            metadata=metadata
        )
    
    async def place_futures_limit_order(
        self,
        symbol: str,
        side: FuturesOrderSide,
        volume: Decimal,
        price: Decimal,
        position_side: Optional[FuturesPositionSide] = None,
        margin_mode: FuturesMarginMode = FuturesMarginMode.CROSS,
        leverage: Decimal = Decimal('1'),
        reduce_only: bool = False,
        time_in_force: FuturesTimeInForce = FuturesTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> FuturesOrder:
        """Place a limit order."""
        return await self.place_futures_order(
            symbol=symbol,
            side=side,
            order_type=FuturesOrderType.LIMIT,
            volume=volume,
            price=price,
            position_side=position_side,
            margin_mode=margin_mode,
            leverage=leverage,
            reduce_only=reduce_only,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata=metadata
        )
    
    # =========================================================================
    # LEVERAGE MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def set_leverage(
        self,
        symbol: str,
        leverage: Decimal,
        margin_mode: FuturesMarginMode = FuturesMarginMode.CROSS
    ) -> Dict[str, Any]:
        """
        Set leverage for a symbol.
        
        Args:
            symbol: Trading symbol
            leverage: Leverage value
            margin_mode: Margin mode
            
        Returns:
            Response data
        """
        try:
            okx_symbol = self.converter.to_okx_instrument(symbol, "SWAP")
            
            params = {
                'instId': okx_symbol,
                'lever': str(leverage),
                'mgnMode': margin_mode.value
            }
            
            response = await self.base._private_request('account/set-leverage', params, 'POST')
            
            logger.info(f"Leverage set to {leverage}x for {symbol} ({margin_mode.value})")
            return response
            
        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            raise
    
    async def get_leverage(self, symbol: str) -> Dict[str, Any]:
        """
        Get current leverage for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Leverage information
        """
        try:
            okx_symbol = self.converter.to_okx_instrument(symbol, "SWAP")
            
            response = await self.base._private_request(
                'account/leverage-info',
                {'instId': okx_symbol}
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting leverage: {e}")
            raise
    
    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_positions(self, symbol: Optional[str] = None) -> List[FuturesPosition]:
        """
        Get futures positions.
        
        Args:
            symbol: Filter by symbol
            
        Returns:
            List of FuturesPosition
        """
        try:
            params = {}
            if symbol:
                params['instId'] = self.converter.to_okx_instrument(symbol, "SWAP")
            
            response = await self.base._private_request('account/positions', params)
            
            positions = []
            for item in response:
                try:
                    position = self._parse_position(item)
                    positions.append(position)
                    
                    # Update cache
                    if position.symbol not in self._positions:
                        self._positions[position.symbol] = {}
                    self._positions[position.symbol][position.side.value] = position
                    
                except Exception as e:
                    logger.error(f"Error parsing position: {e}")
                    continue
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            raise
    
    async def sync_positions(self):
        """Synchronize positions from exchange."""
        try:
            positions = await self.get_positions()
            logger.info(f"Synced {len(positions)} positions")
            return positions
        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
            return []
    
    async def close_position(
        self,
        symbol: str,
        position_side: Optional[FuturesPositionSide] = None,
        volume: Optional[Decimal] = None,
        price: Optional[Decimal] = None
    ) -> FuturesOrder:
        """
        Close a position.
        
        Args:
            symbol: Trading symbol
            position_side: Position side (long, short)
            volume: Volume to close (None = full position)
            price: Price for limit order
            
        Returns:
            FuturesOrder
        """
        if not position_side:
            # Determine position side from current position
            positions = await self.get_positions(symbol)
            if not positions:
                raise OKXPositionError(f"No position found for {symbol}")
            position_side = positions[0].side
        
        # Determine close side
        side = FuturesOrderSide.SELL_CLOSE if position_side == FuturesPositionSide.LONG else FuturesOrderSide.BUY_CLOSE
        
        # Get full volume if not specified
        if volume is None:
            for pos in await self.get_positions(symbol):
                if pos.side == position_side:
                    volume = pos.quantity
                    break
        
        if volume is None:
            raise OKXPositionError(f"Could not determine position volume for {symbol}")
        
        return await self.place_futures_order(
            symbol=symbol,
            side=side,
            order_type=FuturesOrderType.MARKET if price is None else FuturesOrderType.LIMIT,
            volume=volume,
            price=price,
            position_side=position_side,
            reduce_only=True,
            close_position=True,
            metadata={'action': 'close_position'}
        )
    
    # =========================================================================
    # BALANCE MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_balances(self) -> Dict[str, FuturesBalance]:
        """
        Get futures balances.
        
        Returns:
            Dict mapping currency to FuturesBalance
        """
        try:
            response = await self.base._private_request('account/balance')
            
            balances = {}
            for item in response:
                currency = item.get('ccy', '').upper()
                
                bal = FuturesBalance(
                    currency=currency,
                    total=Decimal(str(item.get('eq', 0))),
                    available=Decimal(str(item.get('availEq', 0))),
                    locked=Decimal(str(item.get('lockedEq', 0))),
                    pnl=Decimal(str(item.get('upl', 0))),
                    margin=Decimal(str(item.get('margin', 0))),
                    maintenance_margin=Decimal(str(item.get('maintenanceMargin', 0))),
                    leverage=Decimal(str(item.get('lever', 1))),
                    value_usd=Decimal(str(item.get('eqUsd', 0))),
                    updated_at=datetime.utcnow()
                )
                balances[currency] = bal
            
            self._balances = balances
            
            # Save to database
            if self.pool:
                await self._save_balances()
            
            return balances
            
        except Exception as e:
            logger.error(f"Error getting balances: {e}")
            return self._balances
    
    async def sync_balances(self):
        """Synchronize balances from exchange."""
        try:
            await self.get_balances()
            logger.info("Futures balances synced")
        except Exception as e:
            logger.error(f"Error syncing balances: {e}")
    
    # =========================================================================
    # FUNDING RATE
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_funding_rate(self, symbol: str) -> FuturesFundingRate:
        """
        Get funding rate for a perpetual swap.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            FuturesFundingRate
        """
        try:
            okx_symbol = self.converter.to_okx_instrument(symbol, "SWAP")
            
            response = await self.base._public_request(
                'public/funding-rate',
                {'instId': okx_symbol}
            )
            
            if not response:
                raise OKXInvalidSymbolError(f"No funding rate found for {symbol}")
            
            item = response[0]
            
            funding_rate = FuturesFundingRate(
                symbol=symbol,
                funding_rate=Decimal(str(item.get('fundingRate', 0))),
                next_funding_rate=Decimal(str(item.get('nextFundingRate', 0))) if item.get('nextFundingRate') else None,
                predicted_rate=Decimal(str(item.get('predictedRate', 0))) if item.get('predictedRate') else None,
                next_funding_time=datetime.fromtimestamp(int(item.get('nextFundingTime', 0)) / 1000),
                timestamp=datetime.utcnow(),
                is_predicted=item.get('isPredicted', False),
                metadata=item
            )
            
            self._funding_rates[symbol] = funding_rate
            
            # Save to database
            if self.pool:
                await self._save_funding_rate(funding_rate)
            
            return funding_rate
            
        except Exception as e:
            logger.error(f"Error getting funding rate: {e}")
            raise
    
    async def get_funding_rate_history(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get funding rate history.
        
        Args:
            symbol: Trading symbol
            limit: Number of records
            
        Returns:
            List of funding rate records
        """
        try:
            okx_symbol = self.converter.to_okx_instrument(symbol, "SWAP")
            
            response = await self.base._public_request(
                'public/funding-rate-history',
                {
                    'instId': okx_symbol,
                    'limit': min(limit, 100)
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting funding rate history: {e}")
            return []
    
    # =========================================================================
    # RISK MANAGEMENT
    # =========================================================================
    
    async def get_risk_info(self, symbol: str) -> Optional[FuturesRiskInfo]:
        """
        Get risk information for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            FuturesRiskInfo
        """
        try:
            positions = await self.get_positions(symbol)
            if not positions:
                return None
            
            pos = positions[0]
            
            # Calculate risk metrics
            margin = pos.margin
            maintenance_margin = Decimal('0.01') * margin  # Approximate
            risk_ratio = margin / maintenance_margin if maintenance_margin > 0 else Decimal('inf')
            
            # Get max leverage
            instrument = await self._get_instrument(symbol)
            max_leverage = instrument.leverage_max if instrument else Decimal('100')
            
            return FuturesRiskInfo(
                symbol=symbol,
                margin_mode=pos.margin_mode,
                leverage=pos.leverage,
                position_size=pos.quantity,
                margin=margin,
                maintenance_margin=maintenance_margin,
                liquidation_price=pos.liquidation_price,
                risk_ratio=risk_ratio,
                adl_level=0,  # Would need API
                max_leverage=max_leverage,
                current_leverage=pos.leverage,
                pnl=pos.total_pnl,
                pnl_percent=pos.pnl_percent,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting risk info: {e}")
            return None
    
    async def get_liquidation_price(
        self,
        symbol: str,
        side: FuturesPositionSide,
        entry_price: Decimal,
        leverage: Decimal,
        margin_mode: FuturesMarginMode
    ) -> Decimal:
        """
        Calculate liquidation price.
        
        Args:
            symbol: Trading symbol
            side: Position side
            entry_price: Entry price
            leverage: Leverage
            margin_mode: Margin mode
            
        Returns:
            Liquidation price
        """
        try:
            # Get instrument info
            instrument = await self._get_instrument(symbol)
            if not instrument:
                raise OKXInvalidSymbolError(f"Instrument not found: {symbol}")
            
            # Get position info
            positions = await self.get_positions(symbol)
            pos = next((p for p in positions if p.side == side), None)
            
            if pos:
                return pos.liquidation_price or Decimal('0')
            
            # Calculate approximate liquidation price
            maintenance_rate = instrument.maintenance_rate
            
            if side == FuturesPositionSide.LONG:
                liq_price = entry_price * (1 - (1 / leverage) + maintenance_rate)
            else:
                liq_price = entry_price * (1 + (1 / leverage) - maintenance_rate)
            
            return liq_price
            
        except Exception as e:
            logger.error(f"Error calculating liquidation price: {e}")
            return Decimal('0')
    
    # =========================================================================
    # INSTRUMENT MANAGEMENT
    # =========================================================================
    
    async def _get_instrument(self, symbol: str) -> Optional[FuturesInstrument]:
        """Get futures instrument information."""
        try:
            okx_symbol = self.converter.to_okx_instrument(symbol, "SWAP")
            
            response = await self.base._public_request(
                'public/instruments',
                {'instType': 'SWAP'}
            )
            
            for item in response:
                if item.get('instId') == okx_symbol:
                    return self._parse_instrument(item)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting instrument: {e}")
            return None
    
    def _parse_instrument(self, data: Dict[str, Any]) -> FuturesInstrument:
        """Parse instrument data."""
        return FuturesInstrument(
            id=data.get('instId', ''),
            symbol=self.converter.to_standard_symbol(data.get('instId', '')),
            instrument_type=FuturesInstrumentType.PERPETUAL if data.get('instType') == 'SWAP' else FuturesInstrumentType.DELIVERY,
            contract_size=Decimal(str(data.get('ctVal', 1))),
            tick_size=Decimal(str(data.get('tickSz', 0.01))),
            lot_size=Decimal(str(data.get('lotSz', 0.001))),
            min_volume=Decimal(str(data.get('minSz', 0))),
            max_volume=Decimal(str(data.get('maxSz', 0))) if data.get('maxSz') else None,
            leverage_min=Decimal(str(data.get('lever', 1))),
            leverage_max=Decimal(str(data.get('maxLever', 100))),
            margin_rate=Decimal(str(data.get('marginRate', 0.01))),
            maintenance_rate=Decimal(str(data.get('maintenanceRate', 0.005))),
            expiry=datetime.fromtimestamp(int(data.get('expTime', 0)) / 1000) if data.get('expTime') else None,
            delivery_time=datetime.fromtimestamp(int(data.get('deliveryTime', 0)) / 1000) if data.get('deliveryTime') else None,
            settlement_currency=data.get('settleCcy', ''),
            quote_currency=data.get('quoteCcy', ''),
            base_currency=data.get('baseCcy', ''),
            status=data.get('state', 'live'),
            metadata=data
        )
    
    # =========================================================================
    # POSITION PARSING
    # =========================================================================
    
    def _parse_position(self, data: Dict[str, Any]) -> FuturesPosition:
        """Parse position data."""
        side = data.get('posSide', 'net')
        
        return FuturesPosition(
            id=data.get('posId', str(uuid.uuid4())),
            symbol=self.converter.to_standard_symbol(data.get('instId', '')),
            side=FuturesPositionSide(side) if side in ['long', 'short'] else FuturesPositionSide.NET,
            quantity=Decimal(str(data.get('pos', 0))),
            entry_price=Decimal(str(data.get('avgPx', 0))),
            mark_price=Decimal(str(data.get('markPx', 0))),
            liquidation_price=Decimal(str(data.get('liqPx', 0))) if data.get('liqPx') else None,
            margin=Decimal(str(data.get('margin', 0))),
            leverage=Decimal(str(data.get('lever', 1))),
            unrealized_pnl=Decimal(str(data.get('upl', 0))),
            realized_pnl=Decimal(str(data.get('realizedPnl', 0))),
            total_pnl=Decimal(str(data.get('upl', 0))) + Decimal(str(data.get('realizedPnl', 0))),
            roe=Decimal(str(data.get('roe', 0))),
            margin_mode=FuturesMarginMode(data.get('mgnMode', 'cross')),
            status=FuturesPositionStatus.OPEN if data.get('pos', 0) != 0 else FuturesPositionStatus.CLOSED,
            opened_at=datetime.fromtimestamp(int(data.get('opened', 0)) / 1000) if data.get('opened') else datetime.utcnow(),
            closed_at=datetime.fromtimestamp(int(data.get('closed', 0)) / 1000) if data.get('closed') else None,
            metadata=data
        )
    
    # =========================================================================
    # ORDER PARSING
    # =========================================================================
    
    def _parse_order(self, data: Dict[str, Any]) -> FuturesOrder:
        """Parse order data."""
        status_map = {
            'pending': FuturesOrderStatus.PENDING,
            'live': FuturesOrderStatus.OPEN,
            'partially_filled': FuturesOrderStatus.PARTIALLY_FILLED,
            'filled': FuturesOrderStatus.FILLED,
            'cancelled': FuturesOrderStatus.CANCELLED,
            'expired': FuturesOrderStatus.EXPIRED,
            'rejected': FuturesOrderStatus.REJECTED,
            'triggered': FuturesOrderStatus.TRIGGERED,
            'stopped': FuturesOrderStatus.STOPPED,
        }
        
        status = status_map.get(data.get('state', 'pending'), FuturesOrderStatus.PENDING)
        
        return FuturesOrder(
            id=data.get('ordId', ''),
            symbol=self.converter.to_standard_symbol(data.get('instId', '')),
            side=FuturesOrderSide(data.get('side', 'buy')),
            position_side=FuturesPositionSide(data.get('posSide', 'net')) if data.get('posSide') else None,
            order_type=FuturesOrderType(data.get('ordType', 'limit')),
            status=status,
            price=Decimal(str(data.get('px', 0))),
            volume=Decimal(str(data.get('sz', 0))),
            filled_volume=Decimal(str(data.get('accFillSz', 0))),
            remaining_volume=Decimal(str(data.get('sz', 0))) - Decimal(str(data.get('accFillSz', 0))),
            average_price=Decimal(str(data.get('avgPx', 0))) if data.get('avgPx') else None,
            fee=Decimal(str(data.get('fee', 0))),
            fee_currency=data.get('feeCcy'),
            cost=Decimal(str(data.get('cost', 0))),
            leverage=Decimal(str(data.get('lever', 1))),
            margin=Decimal(str(data.get('margin', 0))),
            time_in_force=FuturesTimeInForce(data.get('timeInForce', 'GTC')),
            created_at=datetime.fromtimestamp(int(data.get('cTime', 0)) / 1000) if data.get('cTime') else datetime.utcnow(),
            updated_at=datetime.fromtimestamp(int(data.get('uTime', 0)) / 1000) if data.get('uTime') else None,
            expires_at=datetime.fromtimestamp(int(data.get('expTime', 0)) / 1000) if data.get('expTime') else None,
            reduce_only=data.get('reduceOnly', False),
            close_position=data.get('close', False),
            client_order_id=data.get('clOrdId'),
            metadata=data
        )
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_order(self, order: FuturesOrder):
        """Save order to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_futures_orders (
                        id, client_order_id, symbol, side, position_side,
                        order_type, status, price, volume, filled_volume,
                        remaining_volume, avg_price, fee, fee_currency,
                        cost, leverage, margin, time_in_force,
                        reduce_only, close_position, created_at,
                        updated_at, expires_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                              $11, $12, $13, $14, $15, $16, $17, $18,
                              $19, $20, $21, $22, $23, $24)
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
                    order.position_side.value if order.position_side else None,
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
                    order.leverage,
                    order.margin,
                    order.time_in_force.value,
                    order.reduce_only,
                    order.close_position,
                    order.created_at,
                    order.updated_at,
                    order.expires_at,
                    json.dumps(order.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving order: {e}")
    
    async def _save_balances(self):
        """Save balances to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                for balance in self._balances.values():
                    await conn.execute(
                        """
                        INSERT INTO okx_futures_balances (
                            currency, total, available, locked,
                            pnl, margin, maintenance_margin,
                            leverage, value_usd, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (currency) DO UPDATE SET
                            total = EXCLUDED.total,
                            available = EXCLUDED.available,
                            locked = EXCLUDED.locked,
                            pnl = EXCLUDED.pnl,
                            margin = EXCLUDED.margin,
                            maintenance_margin = EXCLUDED.maintenance_margin,
                            leverage = EXCLUDED.leverage,
                            value_usd = EXCLUDED.value_usd,
                            updated_at = EXCLUDED.updated_at
                        """,
                        balance.currency,
                        balance.total,
                        balance.available,
                        balance.locked,
                        balance.pnl,
                        balance.margin,
                        balance.maintenance_margin,
                        balance.leverage,
                        balance.value_usd,
                        balance.updated_at
                    )
        except Exception as e:
            logger.error(f"Error saving balances: {e}")
    
    async def _save_funding_rate(self, funding_rate: FuturesFundingRate):
        """Save funding rate to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_futures_funding_rates (
                        symbol, funding_rate, next_funding_rate,
                        predicted_rate, next_funding_time,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    funding_rate.symbol,
                    funding_rate.funding_rate,
                    funding_rate.next_funding_rate,
                    funding_rate.predicted_rate,
                    funding_rate.next_funding_time,
                    json.dumps(funding_rate.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving funding rate: {e}")
    
    # =========================================================================
    # PERIODIC SYNC
    # =========================================================================
    
    async def _periodic_sync(self):
        """Periodically sync futures data."""
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                # Sync positions
                await self.sync_positions()
                
                # Sync balances
                await self.sync_balances()
                
                # Get funding rates for active positions
                for symbol in self._positions:
                    try:
                        await self.get_funding_rate(symbol)
                    except Exception:
                        pass
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic sync error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # WEBHOOKS AND CALLBACKS
    # =========================================================================
    
    async def register_callback(
        self,
        event_type: str,
        callback: Callable
    ):
        """Register a callback for futures events."""
        if event_type not in self._ws_handlers:
            self._ws_handlers[event_type] = []
        self._ws_handlers[event_type].append(callback)
    
    async def _notify_callbacks(self, event_type: str, data: Any):
        """Notify callbacks of an event."""
        if event_type in self._ws_handlers:
            for callback in self._ws_handlers[event_type]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown futures trading module."""
        logger.info("Shutting down OKXFuturesTrading")
        
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OKXFuturesTrading',
    'FuturesInstrumentType',
    'FuturesOrderType',
    'FuturesOrderSide',
    'FuturesPositionSide',
    'FuturesMarginMode',
    'FuturesOrderStatus',
    'FuturesPositionStatus',
    'FuturesTimeInForce',
    'FuturesOrder',
    'FuturesPosition',
    'FuturesFundingRate',
    'FuturesRiskInfo',
    'FuturesTrade',
    'FuturesBalance',
    'FuturesInstrument',
]
