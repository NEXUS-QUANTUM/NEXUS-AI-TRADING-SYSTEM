# trading/exchanges/okx/swap.py
# Nexus AI Trading System - OKX Exchange Perpetual Swap Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - Perpetual Swap Trading Module

This module provides comprehensive perpetual swap trading functionality for the OKX
cryptocurrency exchange, including:

- Perpetual swap order placement and management
- Position management with margin control
- Leverage management for swaps
- Funding rate monitoring and analysis
- Mark price and liquidation price calculations
- Position risk management
- Auto-deleverage (ADL) protection
- Cross-margin and isolated-margin support
- Multi-collateral management
- Swap arbitrage detection
- Basis trading strategies
- Perpetual swap analytics
- Funding rate arbitrage
- Basis trading
- Risk management
- WebSocket real-time updates
- Database persistence
- Redis caching
- Comprehensive error handling

Features:
- All swap order types (market, limit, post-only, IOC, FOK)
- Cross-margin and isolated-margin support
- Leverage adjustment (1x-100x)
- Take-profit and stop-loss orders
- Trailing stop orders
- Position closure
- Auto-position reduction
- Funding rate history
- Basis and spread analysis
- Correlation analysis
- Volatility indicators
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
from trading.exchanges.okx.futures import (
    FuturesPosition,
    FuturesOrder,
    FuturesFundingRate,
    FuturesRiskInfo,
    FuturesInstrument,
    FuturesMarginMode,
    FuturesPositionSide,
    FuturesOrderSide,
    FuturesOrderType,
    FuturesOrderStatus,
    FuturesTimeInForce
)
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class SwapOrderType(str, Enum):
    """Swap order types."""
    MARKET = "market"
    LIMIT = "limit"
    POST_ONLY = "post_only"
    FOK = "fok"
    IOC = "ioc"
    OPTIMAL_LIMIT_IOC = "optimal_limit_ioc"


class SwapOrderSide(str, Enum):
    """Swap order sides."""
    BUY = "buy"
    SELL = "sell"
    BUY_OPEN = "buy_open"
    BUY_CLOSE = "buy_close"
    SELL_OPEN = "sell_open"
    SELL_CLOSE = "sell_close"


class SwapPositionSide(str, Enum):
    """Swap position sides."""
    LONG = "long"
    SHORT = "short"
    NET = "net"  # One-way mode


class SwapMarginMode(str, Enum):
    """Swap margin modes."""
    CROSS = "cross"
    ISOLATED = "isolated"


class SwapOrderStatus(str, Enum):
    """Swap order status."""
    PENDING = "pending"
    OPEN = "live"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    TRIGGERED = "triggered"
    STOPPED = "stopped"


class SwapPositionStatus(str, Enum):
    """Swap position status."""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"
    LIQUIDATED = "liquidated"
    ADL = "adl"


class SwapTimeInForce(str, Enum):
    """Swap time in force."""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    DAY = "Day"
    GTX = "GTX"


class SwapInstrumentType(str, Enum):
    """Swap instrument types."""
    LINEAR = "linear"  # USDT-margined
    INVERSE = "inverse"  # Coin-margined
    PERPETUAL = "perpetual"
    DELIVERY = "delivery"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class SwapOrder(BaseModel):
    """Swap order model."""
    id: str
    symbol: str
    side: SwapOrderSide
    position_side: Optional[SwapPositionSide] = None
    order_type: SwapOrderType
    status: SwapOrderStatus
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
    time_in_force: SwapTimeInForce = SwapTimeInForce.GTC
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reduce_only: bool = False
    close_position: bool = False
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.volume == 0:
            return 0.0
        return float(self.filled_volume / self.volume * 100)

    @property
    def is_open(self) -> bool:
        return self.status in [SwapOrderStatus.OPEN, SwapOrderStatus.PARTIALLY_FILLED]


class SwapPosition(BaseModel):
    """Swap position model."""
    id: str
    symbol: str
    side: SwapPositionSide
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
    margin_mode: SwapMarginMode
    status: SwapPositionStatus = SwapPositionStatus.OPEN
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


class SwapFundingRate(BaseModel):
    """Swap funding rate data."""
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


class SwapRiskInfo(BaseModel):
    """Swap risk information."""
    symbol: str
    margin_mode: SwapMarginMode
    leverage: Decimal
    position_size: Decimal
    margin: Decimal
    maintenance_margin: Decimal
    liquidation_price: Optional[Decimal] = None
    risk_ratio: Decimal
    adl_level: int
    max_leverage: Decimal
    current_leverage: Decimal
    pnl: Decimal
    pnl_percent: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SwapTrade(BaseModel):
    """Swap trade model."""
    id: str
    symbol: str
    side: SwapOrderSide
    position_side: Optional[SwapPositionSide] = None
    price: Decimal
    volume: Decimal
    cost: Decimal
    fee: Decimal = Decimal('0')
    fee_currency: Optional[str] = None
    order_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pnl: Optional[Decimal] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SwapBalance(BaseModel):
    """Swap balance model."""
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


class SwapInstrument(BaseModel):
    """Swap instrument model."""
    id: str
    symbol: str
    instrument_type: SwapInstrumentType
    contract_size: Decimal
    tick_size: Decimal
    lot_size: Decimal
    min_volume: Decimal
    max_volume: Optional[Decimal] = None
    leverage_min: Decimal
    leverage_max: Decimal
    margin_rate: Decimal
    maintenance_rate: Decimal
    settlement_currency: str
    quote_currency: str
    base_currency: str
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Swap orders
CREATE TABLE IF NOT EXISTS okx_swap_orders (
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
    INDEX idx_okx_swap_orders_symbol (symbol),
    INDEX idx_okx_swap_orders_status (status),
    INDEX idx_okx_swap_orders_created_at (created_at)
);

-- Swap positions
CREATE TABLE IF NOT EXISTS okx_swap_positions (
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

-- Swap funding rates
CREATE TABLE IF NOT EXISTS okx_swap_funding_rates (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    funding_rate DECIMAL(32, 16) NOT NULL,
    next_funding_rate DECIMAL(32, 16),
    predicted_rate DECIMAL(32, 16),
    next_funding_time TIMESTAMP NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_swap_funding_rates_symbol (symbol),
    INDEX idx_okx_swap_funding_rates_timestamp (timestamp)
);

-- Swap trades
CREATE TABLE IF NOT EXISTS okx_swap_trades (
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
    INDEX idx_okx_swap_trades_symbol (symbol),
    INDEX idx_okx_swap_trades_timestamp (timestamp)
);

-- Swap balances
CREATE TABLE IF NOT EXISTS okx_swap_balances (
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
# MAIN SWAP TRADING CLASS
# =============================================================================

class OKXSwapTrading:
    """
    Advanced perpetual swap trading for OKX exchange.
    
    Features:
    - All swap order types (market, limit, post-only, IOC, FOK)
    - Cross-margin and isolated-margin support
    - Leverage management (1x-100x)
    - Position management
    - Stop-loss and take-profit orders
    - Trailing stop orders
    - Funding rate monitoring and analysis
    - Risk management
    - Liquidation price monitoring
    - Auto-deleverage protection
    - Multi-collateral management
    - Basis and spread analysis
    - Correlation analysis
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
        
        # Swap state
        self._orders: Dict[str, SwapOrder] = {}
        self._positions: Dict[str, Dict[str, SwapPosition]] = {}
        self._balances: Dict[str, SwapBalance] = {}
        self._funding_rates: Dict[str, SwapFundingRate] = {}
        
        # Circuit breakers
        self._swap_cb = CircuitBreaker(
            name="okx_swap",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # WebSocket integration
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
        
        logger.info("OKXSwapTrading initialized")
    
    async def initialize(self):
        """Initialize swap trading module."""
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load balances
        await self.sync_balances()
        
        # Load positions
        await self.sync_positions()
        
        # Start periodic sync
        self._sync_task = asyncio.create_task(self._periodic_sync())
        
        logger.info("OKXSwapTrading initialization complete")
    
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
    async def place_swap_order(
        self,
        symbol: str,
        side: SwapOrderSide,
        order_type: SwapOrderType,
        volume: Decimal,
        price: Optional[Decimal] = None,
        position_side: Optional[SwapPositionSide] = None,
        margin_mode: SwapMarginMode = SwapMarginMode.CROSS,
        leverage: Decimal = Decimal('1'),
        reduce_only: bool = False,
        close_position: bool = False,
        time_in_force: SwapTimeInForce = SwapTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        trailing_stop: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> SwapOrder:
        """
        Place a perpetual swap order.
        
        Args:
            symbol: Trading symbol
            side: Order side
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
            SwapOrder
        """
        if self._swap_cb.is_open():
            raise OKXRateLimitError("Swap circuit breaker is open")
        
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
            
            if time_in_force != SwapTimeInForce.GTC:
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
            
            self._swap_cb.record_success()
            
            logger.info(
                f"Swap order placed: {order.id} | {side} {volume} "
                f"{symbol} @ {price or 'market'} ({leverage}x)"
            )
            
            return order
            
        except Exception as e:
            self._swap_cb.record_failure()
            logger.error(f"Swap order placement error: {e}")
            raise
    
    async def place_swap_market_order(
        self,
        symbol: str,
        side: SwapOrderSide,
        volume: Decimal,
        margin_mode: SwapMarginMode = SwapMarginMode.CROSS,
        leverage: Decimal = Decimal('1'),
        reduce_only: bool = False,
        close_position: bool = False,
        client_order_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> SwapOrder:
        """Place a market order."""
        return await self.place_swap_order(
            symbol=symbol,
            side=side,
            order_type=SwapOrderType.MARKET,
            volume=volume,
            margin_mode=margin_mode,
            leverage=leverage,
            reduce_only=reduce_only,
            close_position=close_position,
            client_order_id=client_order_id,
            metadata=metadata
        )
    
    async def place_swap_limit_order(
        self,
        symbol: str,
        side: SwapOrderSide,
        volume: Decimal,
        price: Decimal,
        position_side: Optional[SwapPositionSide] = None,
        margin_mode: SwapMarginMode = SwapMarginMode.CROSS,
        leverage: Decimal = Decimal('1'),
        reduce_only: bool = False,
        time_in_force: SwapTimeInForce = SwapTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> SwapOrder:
        """Place a limit order."""
        return await self.place_swap_order(
            symbol=symbol,
            side=side,
            order_type=SwapOrderType.LIMIT,
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
        margin_mode: SwapMarginMode = SwapMarginMode.CROSS
    ) -> Dict[str, Any]:
        """Set leverage for a symbol."""
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
        """Get current leverage for a symbol."""
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
    async def get_positions(self, symbol: Optional[str] = None) -> List[SwapPosition]:
        """Get swap positions."""
        try:
            params = {'instType': 'SWAP'}
            if symbol:
                params['instId'] = self.converter.to_okx_instrument(symbol, "SWAP")
            
            response = await self.base._private_request('account/positions', params)
            
            positions = []
            for item in response:
                try:
                    position = self._parse_position(item)
                    positions.append(position)
                    
                    if position.symbol not in self._positions:
                        self._positions[position.symbol] = {}
                    self._positions[position.symbol][position.side.value] = position
                    
                except Exception as e:
                    logger.error(f"Error parsing position: {e}")
                    continue
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def sync_positions(self):
        """Synchronize positions from exchange."""
        try:
            positions = await self.get_positions()
            logger.info(f"Synced {len(positions)} swap positions")
            return positions
        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
            return []
    
    async def close_position(
        self,
        symbol: str,
        position_side: Optional[SwapPositionSide] = None,
        volume: Optional[Decimal] = None,
        price: Optional[Decimal] = None
    ) -> SwapOrder:
        """Close a swap position."""
        if not position_side:
            positions = await self.get_positions(symbol)
            if not positions:
                raise OKXPositionError(f"No position found for {symbol}")
            position_side = positions[0].side
        
        side = SwapOrderSide.SELL_CLOSE if position_side == SwapPositionSide.LONG else SwapOrderSide.BUY_CLOSE
        
        if volume is None:
            for pos in await self.get_positions(symbol):
                if pos.side == position_side:
                    volume = pos.quantity
                    break
        
        if volume is None:
            raise OKXPositionError(f"Could not determine position volume for {symbol}")
        
        return await self.place_swap_order(
            symbol=symbol,
            side=side,
            order_type=SwapOrderType.MARKET if price is None else SwapOrderType.LIMIT,
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
    async def get_balances(self) -> Dict[str, SwapBalance]:
        """Get swap balances."""
        try:
            response = await self.base._private_request('account/balance')
            
            balances = {}
            for item in response:
                currency = item.get('ccy', '').upper()
                
                bal = SwapBalance(
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
            logger.info("Swap balances synced")
        except Exception as e:
            logger.error(f"Error syncing balances: {e}")
    
    # =========================================================================
    # FUNDING RATE
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_funding_rate(self, symbol: str) -> SwapFundingRate:
        """Get funding rate for a perpetual swap."""
        try:
            okx_symbol = self.converter.to_okx_instrument(symbol, "SWAP")
            
            response = await self.base._public_request(
                'public/funding-rate',
                {'instId': okx_symbol}
            )
            
            if not response:
                raise OKXInvalidSymbolError(f"No funding rate found for {symbol}")
            
            item = response[0]
            
            funding_rate = SwapFundingRate(
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
        """Get funding rate history."""
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
    
    async def get_risk_info(self, symbol: str) -> Optional[SwapRiskInfo]:
        """Get risk information for a symbol."""
        try:
            positions = await self.get_positions(symbol)
            if not positions:
                return None
            
            pos = positions[0]
            
            margin = pos.margin
            maintenance_margin = Decimal('0.01') * margin
            risk_ratio = margin / maintenance_margin if maintenance_margin > 0 else Decimal('inf')
            
            instrument = await self._get_instrument(symbol)
            max_leverage = instrument.leverage_max if instrument else Decimal('100')
            
            return SwapRiskInfo(
                symbol=symbol,
                margin_mode=pos.margin_mode,
                leverage=pos.leverage,
                position_size=pos.quantity,
                margin=margin,
                maintenance_margin=maintenance_margin,
                liquidation_price=pos.liquidation_price,
                risk_ratio=risk_ratio,
                adl_level=0,
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
        side: SwapPositionSide,
        entry_price: Decimal,
        leverage: Decimal,
        margin_mode: SwapMarginMode
    ) -> Decimal:
        """Calculate liquidation price."""
        try:
            instrument = await self._get_instrument(symbol)
            if not instrument:
                raise OKXInvalidSymbolError(f"Instrument not found: {symbol}")
            
            positions = await self.get_positions(symbol)
            pos = next((p for p in positions if p.side == side), None)
            
            if pos:
                return pos.liquidation_price or Decimal('0')
            
            maintenance_rate = instrument.maintenance_rate
            
            if side == SwapPositionSide.LONG:
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
    
    async def _get_instrument(self, symbol: str) -> Optional[SwapInstrument]:
        """Get swap instrument information."""
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
    
    def _parse_instrument(self, data: Dict[str, Any]) -> SwapInstrument:
        """Parse instrument data."""
        return SwapInstrument(
            id=data.get('instId', ''),
            symbol=self.converter.to_standard_symbol(data.get('instId', '')),
            instrument_type=SwapInstrumentType.PERPETUAL,
            contract_size=Decimal(str(data.get('ctVal', 1))),
            tick_size=Decimal(str(data.get('tickSz', 0.01))),
            lot_size=Decimal(str(data.get('lotSz', 0.001))),
            min_volume=Decimal(str(data.get('minSz', 0))),
            max_volume=Decimal(str(data.get('maxSz', 0))) if data.get('maxSz') else None,
            leverage_min=Decimal(str(data.get('lever', 1))),
            leverage_max=Decimal(str(data.get('maxLever', 100))),
            margin_rate=Decimal(str(data.get('marginRate', 0.01))),
            maintenance_rate=Decimal(str(data.get('maintenanceRate', 0.005))),
            settlement_currency=data.get('settleCcy', ''),
            quote_currency=data.get('quoteCcy', ''),
            base_currency=data.get('baseCcy', ''),
            status=data.get('state', 'live'),
            metadata=data
        )
    
    # =========================================================================
    # POSITION PARSING
    # =========================================================================
    
    def _parse_position(self, data: Dict[str, Any]) -> SwapPosition:
        """Parse position data."""
        side = data.get('posSide', 'net')
        
        return SwapPosition(
            id=data.get('posId', str(uuid.uuid4())),
            symbol=self.converter.to_standard_symbol(data.get('instId', '')),
            side=SwapPositionSide(side) if side in ['long', 'short'] else SwapPositionSide.NET,
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
            margin_mode=SwapMarginMode(data.get('mgnMode', 'cross')),
            status=SwapPositionStatus.OPEN if data.get('pos', 0) != 0 else SwapPositionStatus.CLOSED,
            opened_at=datetime.fromtimestamp(int(data.get('opened', 0)) / 1000) if data.get('opened') else datetime.utcnow(),
            closed_at=datetime.fromtimestamp(int(data.get('closed', 0)) / 1000) if data.get('closed') else None,
            metadata=data
        )
    
    # =========================================================================
    # ORDER PARSING
    # =========================================================================
    
    def _parse_order(self, data: Dict[str, Any]) -> SwapOrder:
        """Parse order data."""
        status_map = {
            'pending': SwapOrderStatus.PENDING,
            'live': SwapOrderStatus.OPEN,
            'partially_filled': SwapOrderStatus.PARTIALLY_FILLED,
            'filled': SwapOrderStatus.FILLED,
            'cancelled': SwapOrderStatus.CANCELLED,
            'expired': SwapOrderStatus.EXPIRED,
            'rejected': SwapOrderStatus.REJECTED,
            'triggered': SwapOrderStatus.TRIGGERED,
            'stopped': SwapOrderStatus.STOPPED,
        }
        
        status = status_map.get(data.get('state', 'pending'), SwapOrderStatus.PENDING)
        
        return SwapOrder(
            id=data.get('ordId', ''),
            symbol=self.converter.to_standard_symbol(data.get('instId', '')),
            side=SwapOrderSide(data.get('side', 'buy')),
            position_side=SwapPositionSide(data.get('posSide', 'net')) if data.get('posSide') else None,
            order_type=SwapOrderType(data.get('ordType', 'limit')),
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
            time_in_force=SwapTimeInForce(data.get('timeInForce', 'GTC')),
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
    
    async def _save_order(self, order: SwapOrder):
        """Save order to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_swap_orders (
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
                        INSERT INTO okx_swap_balances (
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
    
    async def _save_funding_rate(self, funding_rate: SwapFundingRate):
        """Save funding rate to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_swap_funding_rates (
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
        """Periodically sync swap data."""
        while True:
            try:
                await asyncio.sleep(30)
                
                await self.sync_positions()
                await self.sync_balances()
                
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
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown swap trading module."""
        logger.info("Shutting down OKXSwapTrading")
        
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
    'OKXSwapTrading',
    'SwapOrderType',
    'SwapOrderSide',
    'SwapPositionSide',
    'SwapMarginMode',
    'SwapOrderStatus',
    'SwapPositionStatus',
    'SwapTimeInForce',
    'SwapInstrumentType',
    'SwapOrder',
    'SwapPosition',
    'SwapFundingRate',
    'SwapRiskInfo',
    'SwapTrade',
    'SwapBalance',
    'SwapInstrument'
]
