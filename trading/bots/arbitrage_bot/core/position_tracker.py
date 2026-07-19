# trading/bots/arbitrage_bot/core/position_tracker.py
# Nexus AI Trading System - Arbitrage Bot Position Tracker Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Position Tracker Module

This module provides comprehensive position tracking and monitoring
for the arbitrage bot system, including:

- Real-time position tracking across exchanges
- Multi-leg position management
- Position P&L calculation and tracking
- Position health monitoring
- Position alerts and notifications
- Position history and analytics
- Position reconciliation
- Position risk monitoring
- Position performance metrics
- Position correlation analysis
- Position exit strategy management
- Position hedging
- Position scaling
- Position averaging
- Partial position management
- Position lifecycle tracking

The position tracker ensures accurate monitoring and management
of all positions across multiple exchanges and strategies.
"""

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import numpy as np
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.exchange_connector import (
    ExchangeConnector,
    ExchangeOrder,
    ExchangeOrderStatus
)
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketPrice
from trading.bots.arbitrage_bot.core.balance_manager import BalanceManager
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class PositionStatus(str, Enum):
    """Position status."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"
    STOPPED = "stopped"
    EXPIRED = "expired"
    ERROR = "error"


class PositionLegStatus(str, Enum):
    """Position leg status."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PositionSide(str, Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"
    NET = "net"


class PositionType(str, Enum):
    """Position types."""
    SINGLE = "single"          # Single leg position
    SPREAD = "spread"          # Spread position
    ARBITRAGE = "arbitrage"    # Arbitrage position
    HEDGE = "hedge"            # Hedge position
    MULTI_LEG = "multi_leg"    # Multi-leg position
    BASKET = "basket"          # Basket position


class PositionExitReason(str, Enum):
    """Position exit reasons."""
    TARGET_REACHED = "target_reached"
    STOP_LOSS = "stop_loss"
    TIMEOUT = "timeout"
    MANUAL = "manual"
    LIQUIDATION = "liquidation"
    REBALANCE = "rebalance"
    RISK_LIMIT = "risk_limit"
    MARKET_CONDITION = "market_condition"
    ERROR = "error"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PositionLeg(BaseModel):
    """Position leg."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    side: PositionSide
    entry_price: Decimal
    current_price: Decimal
    quantity: Decimal
    filled_quantity: Decimal = Decimal('0')
    status: PositionLegStatus = PositionLegStatus.PENDING
    order_id: Optional[str] = None
    entry_time: datetime = Field(default_factory=datetime.utcnow)
    filled_time: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def market_value(self) -> Decimal:
        """Calculate market value."""
        return self.filled_quantity * self.current_price

    @property
    def cost_basis(self) -> Decimal:
        """Calculate cost basis."""
        return self.filled_quantity * self.entry_price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P&L."""
        if self.side == PositionSide.LONG:
            return self.filled_quantity * (self.current_price - self.entry_price)
        else:
            return self.filled_quantity * (self.entry_price - self.current_price)

    @property
    def is_filled(self) -> bool:
        """Check if leg is filled."""
        return self.status == PositionLegStatus.FILLED


class Position(BaseModel):
    """Position model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: Optional[str] = None
    type: PositionType = PositionType.SINGLE
    status: PositionStatus = PositionStatus.PENDING
    
    # Position details
    legs: List[PositionLeg] = Field(default_factory=list)
    total_quantity: Decimal = Decimal('0')
    average_entry_price: Decimal = Decimal('0')
    current_price: Decimal = Decimal('0')
    market_value: Decimal = Decimal('0')
    cost_basis: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    pnl_percent: Decimal = Decimal('0')
    
    # Risk management
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    trailing_stop: Optional[Decimal] = None
    risk_reward_ratio: Optional[Decimal] = None
    
    # Timing
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    exit_reason: Optional[PositionExitReason] = None
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        """Check if position is open."""
        return self.status in [PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED]

    @property
    def is_profitable(self) -> bool:
        """Check if position is profitable."""
        return self.total_pnl > 0

    @property
    def days_open(self) -> float:
        """Calculate days open."""
        if self.closed_at:
            return (self.closed_at - self.opened_at).total_seconds() / 86400
        return (datetime.utcnow() - self.opened_at).total_seconds() / 86400

    @property
    def fill_rate(self) -> Decimal:
        """Calculate fill rate."""
        total_filled = sum(leg.filled_quantity for leg in self.legs)
        total_quantity = self.total_quantity
        if total_quantity == 0:
            return Decimal('0')
        return total_filled / total_quantity

    @property
    def is_fully_filled(self) -> bool:
        """Check if position is fully filled."""
        return self.fill_rate >= Decimal('0.99')


class PositionAlert(BaseModel):
    """Position alert."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str
    type: str  # 'price', 'pnl', 'drawdown', 'time'
    severity: str  # 'info', 'warning', 'critical'
    message: str
    value: Decimal
    threshold: Decimal
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PositionSummary(BaseModel):
    """Position summary."""
    total_positions: int = 0
    open_positions: int = 0
    closed_positions: int = 0
    total_pnl: Decimal = Decimal('0')
    average_pnl: Decimal = Decimal('0')
    win_rate: Decimal = Decimal('0')
    profitable_positions: int = 0
    losing_positions: int = 0
    average_days_open: float = 0.0
    max_pnl: Decimal = Decimal('0')
    min_pnl: Decimal = Decimal('0')
    total_volume: Decimal = Decimal('0')
    total_fees: Decimal = Decimal('0')


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Positions
CREATE TABLE IF NOT EXISTS tracker_positions (
    id VARCHAR(64) PRIMARY KEY,
    strategy_id VARCHAR(64),
    type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_quantity DECIMAL(32, 16) NOT NULL,
    avg_entry_price DECIMAL(32, 16) NOT NULL,
    current_price DECIMAL(32, 16) NOT NULL,
    market_value DECIMAL(32, 16) NOT NULL,
    cost_basis DECIMAL(32, 16) NOT NULL,
    unrealized_pnl DECIMAL(32, 16) NOT NULL,
    realized_pnl DECIMAL(32, 16) DEFAULT 0,
    total_pnl DECIMAL(32, 16) NOT NULL,
    pnl_percent DECIMAL(32, 16) NOT NULL,
    stop_loss DECIMAL(32, 16),
    take_profit DECIMAL(32, 16),
    trailing_stop DECIMAL(32, 16),
    risk_reward_ratio DECIMAL(32, 16),
    opened_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    exit_reason VARCHAR(30),
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    INDEX idx_tracker_positions_strategy_id (strategy_id),
    INDEX idx_tracker_positions_status (status),
    INDEX idx_tracker_positions_opened_at (opened_at)
);

-- Position legs
CREATE TABLE IF NOT EXISTS tracker_position_legs (
    id VARCHAR(64) PRIMARY KEY,
    position_id VARCHAR(64) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    entry_price DECIMAL(32, 16) NOT NULL,
    current_price DECIMAL(32, 16) NOT NULL,
    quantity DECIMAL(32, 16) NOT NULL,
    filled_quantity DECIMAL(32, 16) DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    order_id VARCHAR(64),
    entry_time TIMESTAMP NOT NULL,
    filled_time TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_tracker_position_legs_position_id (position_id),
    INDEX idx_tracker_position_legs_status (status)
);

-- Position alerts
CREATE TABLE IF NOT EXISTS tracker_position_alerts (
    id VARCHAR(64) PRIMARY KEY,
    position_id VARCHAR(64) NOT NULL,
    type VARCHAR(30) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    value DECIMAL(32, 16) NOT NULL,
    threshold DECIMAL(32, 16) NOT NULL,
    triggered_at TIMESTAMP NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    INDEX idx_tracker_position_alerts_position_id (position_id),
    INDEX idx_tracker_position_alerts_triggered_at (triggered_at)
);

-- Position history
CREATE TABLE IF NOT EXISTS tracker_position_history (
    id SERIAL PRIMARY KEY,
    position_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL,
    price DECIMAL(32, 16) NOT NULL,
    pnl DECIMAL(32, 16) NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_tracker_position_history_position_id (position_id),
    INDEX idx_tracker_position_history_timestamp (timestamp)
);
"""


# =============================================================================
# POSITION TRACKER CLASS
# =============================================================================

class PositionTracker:
    """
    Advanced position tracker for arbitrage bot.
    
    Features:
    - Real-time position tracking across exchanges
    - Multi-leg position management
    - Position P&L calculation and tracking
    - Position health monitoring
    - Position alerts and notifications
    - Position history and analytics
    - Position reconciliation
    - Position risk monitoring
    - Position performance metrics
    - Position correlation analysis
    - Position exit strategy management
    - Position hedging
    - Position scaling
    - Position averaging
    - Partial position management
    - Position lifecycle tracking
    """
    
    def __init__(
        self,
        market_data: MarketDataManager,
        balance_manager: BalanceManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.market_data = market_data
        self.balance_manager = balance_manager
        self.redis = redis
        self.pool = pool
        self.config = config or {}
        
        # Positions
        self._positions: Dict[str, Position] = {}
        
        # Alerts
        self._alerts: List[PositionAlert] = []
        
        # Exchange connectors
        self._connectors: Dict[str, ExchangeConnector] = {}
        
        # Circuit breakers
        self._tracker_cb = CircuitBreaker(
            name="position_tracker",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            "position_open": [],
            "position_update": [],
            "position_close": [],
            "position_alert": [],
            "position_leg_update": []
        }
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Update task
        self._update_task: Optional[asyncio.Task] = None
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info("PositionTracker initialized")
    
    async def initialize(self):
        """Initialize the position tracker."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load positions
        if self.pool:
            await self._load_positions()
        
        # Start update loop
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        
        self._initialized = True
        logger.info("PositionTracker initialized")
    
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
    # CONNECTOR MANAGEMENT
    # =========================================================================
    
    def register_connector(self, connector: ExchangeConnector):
        """
        Register an exchange connector.
        
        Args:
            connector: Exchange connector instance
        """
        self._connectors[connector.config.exchange] = connector
        logger.info(f"Registered connector for {connector.config.exchange}")
    
    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================
    
    async def create_position(
        self,
        legs: List[Dict[str, Any]],
        position_type: PositionType = PositionType.SINGLE,
        strategy_id: Optional[str] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        trailing_stop: Optional[Decimal] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Position:
        """
        Create a new position.
        
        Args:
            legs: List of leg configurations
            position_type: Type of position
            strategy_id: Strategy ID
            stop_loss: Stop loss price
            take_profit: Take profit price
            trailing_stop: Trailing stop price
            tags: Position tags
            metadata: Additional metadata
            
        Returns:
            Position
        """
        if self._tracker_cb.is_open():
            raise CircuitBreakerOpenError("Position tracker circuit breaker is open")
        
        try:
            # Create position legs
            position_legs = []
            for leg_data in legs:
                leg = PositionLeg(
                    exchange=leg_data['exchange'],
                    symbol=leg_data['symbol'],
                    side=PositionSide(leg_data.get('side', 'long')),
                    entry_price=leg_data['entry_price'],
                    current_price=leg_data['entry_price'],
                    quantity=leg_data['quantity'],
                    entry_time=datetime.utcnow(),
                    metadata=leg_data.get('metadata', {})
                )
                position_legs.append(leg)
            
            # Calculate position totals
            total_quantity = sum(leg.quantity for leg in position_legs)
            avg_entry = sum(leg.entry_price * leg.quantity for leg in position_legs) / total_quantity if total_quantity > 0 else Decimal('0')
            cost_basis = sum(leg.entry_price * leg.quantity for leg in position_legs)
            
            # Create position
            position = Position(
                strategy_id=strategy_id,
                type=position_type,
                legs=position_legs,
                total_quantity=total_quantity,
                average_entry_price=avg_entry,
                current_price=avg_entry,
                cost_basis=cost_basis,
                market_value=cost_basis,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_stop=trailing_stop,
                opened_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                tags=tags or [],
                metadata=metadata or {}
            )
            
            # Calculate risk-reward ratio
            if stop_loss and take_profit:
                risk = abs(avg_entry - stop_loss)
                reward = abs(take_profit - avg_entry)
                if risk > 0:
                    position.risk_reward_ratio = reward / risk
            
            # Add to tracker
            async with self._lock:
                self._positions[position.id] = position
            
            # Save to database
            if self.pool:
                await self._save_position(position)
                for leg in position.legs:
                    await self._save_leg(leg, position.id)
            
            # Record success
            self._tracker_cb.record_success()
            
            # Trigger callbacks
            await self._trigger_callbacks("position_open", position)
            
            logger.info(
                f"Created position {position.id}: {position.type.value} "
                f"legs={len(position.legs)} quantity={position.total_quantity}"
            )
            
            return position
            
        except Exception as e:
            self._tracker_cb.record_failure()
            logger.error(f"Error creating position: {e}")
            raise
    
    async def update_position(
        self,
        position_id: str,
        price_updates: Optional[Dict[str, Decimal]] = None,
        leg_updates: Optional[Dict[str, Dict[str, Any]]] = None,
        status: Optional[PositionStatus] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Position]:
        """
        Update a position.
        
        Args:
            position_id: Position ID
            price_updates: Price updates per symbol
            leg_updates: Leg updates per leg ID
            status: New position status
            metadata: Additional metadata
            
        Returns:
            Updated Position or None
        """
        if position_id not in self._positions:
            return None
        
        position = self._positions[position_id]
        
        # Update legs
        if leg_updates:
            for leg in position.legs:
                if leg.id in leg_updates:
                    update = leg_updates[leg.id]
                    if 'filled_quantity' in update:
                        leg.filled_quantity = update['filled_quantity']
                    if 'status' in update:
                        leg.status = PositionLegStatus(update['status'])
                    if 'current_price' in update:
                        leg.current_price = update['current_price']
                    if 'order_id' in update:
                        leg.order_id = update['order_id']
                    if 'filled_time' in update:
                        leg.filled_time = update['filled_time']
        
        # Update prices
        if price_updates:
            for symbol, price in price_updates.items():
                for leg in position.legs:
                    if leg.symbol == symbol:
                        leg.current_price = price
        
        # Calculate position metrics
        total_quantity = sum(leg.filled_quantity for leg in position.legs)
        if total_quantity > 0:
            weighted_price = sum(leg.entry_price * leg.filled_quantity for leg in position.legs) / total_quantity
            position.average_entry_price = weighted_price
        else:
            position.average_entry_price = Decimal('0')
        
        position.total_quantity = total_quantity
        
        # Update current price (average of leg current prices)
        if position.legs:
            position.current_price = sum(leg.current_price for leg in position.legs) / len(position.legs)
        
        # Calculate cost basis and market value
        position.cost_basis = sum(leg.entry_price * leg.filled_quantity for leg in position.legs)
        position.market_value = sum(leg.current_price * leg.filled_quantity for leg in position.legs)
        
        # Calculate P&L
        position.unrealized_pnl = sum(leg.unrealized_pnl for leg in position.legs)
        position.total_pnl = position.unrealized_pnl + position.realized_pnl
        
        # Calculate P&L percentage
        if position.cost_basis > 0:
            position.pnl_percent = position.total_pnl / position.cost_basis * 100
        else:
            position.pnl_percent = Decimal('0')
        
        # Update status
        if status:
            position.status = status
        
        # Update metadata
        if metadata:
            position.metadata.update(metadata)
        
        position.updated_at = datetime.utcnow()
        
        # Save to database
        if self.pool:
            await self._update_position(position)
            for leg in position.legs:
                await self._update_leg(leg)
        
        # Trigger callbacks
        await self._trigger_callbacks("position_update", position)
        
        # Check for alerts
        await self._check_alerts(position)
        
        # Check exit conditions
        await self._check_exit_conditions(position)
        
        return position
    
    async def close_position(
        self,
        position_id: str,
        exit_reason: PositionExitReason = PositionExitReason.MANUAL,
        closing_prices: Optional[Dict[str, Decimal]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Close a position.
        
        Args:
            position_id: Position ID
            exit_reason: Exit reason
            closing_prices: Closing prices per symbol
            metadata: Additional metadata
            
        Returns:
            True if closed successfully
        """
        if position_id not in self._positions:
            return False
        
        position = self._positions[position_id]
        
        if position.status == PositionStatus.CLOSED:
            return False
        
        # Update closing prices
        if closing_prices:
            for symbol, price in closing_prices.items():
                for leg in position.legs:
                    if leg.symbol == symbol:
                        leg.current_price = price
        
        # Calculate final P&L
        position.unrealized_pnl = sum(leg.unrealized_pnl for leg in position.legs)
        position.total_pnl = position.unrealized_pnl + position.realized_pnl
        
        # Update position
        position.status = PositionStatus.CLOSED
        position.closed_at = datetime.utcnow()
        position.exit_reason = exit_reason
        position.updated_at = datetime.utcnow()
        
        if metadata:
            position.metadata.update(metadata)
        
        # Save to database
        if self.pool:
            await self._update_position(position)
        
        # Trigger callbacks
        await self._trigger_callbacks("position_close", position)
        
        logger.info(f"Closed position {position_id}: {exit_reason.value}")
        return True
    
    # =========================================================================
    # POSITION QUERYING
    # =========================================================================
    
    async def get_position(self, position_id: str) -> Optional[Position]:
        """
        Get a position by ID.
        
        Args:
            position_id: Position ID
            
        Returns:
            Position or None
        """
        return self._positions.get(position_id)
    
    async def get_open_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of open positions
        """
        return [p for p in self._positions.values() if p.is_open]
    
    async def get_positions_by_strategy(
        self,
        strategy_id: str
    ) -> List[Position]:
        """
        Get positions by strategy ID.
        
        Args:
            strategy_id: Strategy ID
            
        Returns:
            List of positions
        """
        return [p for p in self._positions.values() if p.strategy_id == strategy_id]
    
    async def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """
        Get positions by symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            List of positions
        """
        return [p for p in self._positions.values() if any(leg.symbol == symbol for leg in p.legs)]
    
    async def get_summary(self) -> PositionSummary:
        """
        Get position summary.
        
        Returns:
            PositionSummary
        """
        positions = list(self._positions.values())
        
        open_positions = [p for p in positions if p.is_open]
        closed_positions = [p for p in positions if p.status == PositionStatus.CLOSED]
        
        total_pnl = sum(p.total_pnl for p in positions)
        profitable = [p for p in positions if p.is_profitable]
        losing = [p for p in positions if not p.is_profitable and p.total_pnl < 0]
        
        avg_days = sum(p.days_open for p in positions) / len(positions) if positions else 0
        
        return PositionSummary(
            total_positions=len(positions),
            open_positions=len(open_positions),
            closed_positions=len(closed_positions),
            total_pnl=total_pnl,
            average_pnl=total_pnl / len(positions) if positions else Decimal('0'),
            win_rate=Decimal(str(len(profitable) / len(positions))) if positions else Decimal('0'),
            profitable_positions=len(profitable),
            losing_positions=len(losing),
            average_days_open=avg_days,
            max_pnl=max((p.total_pnl for p in positions), default=Decimal('0')),
            min_pnl=min((p.total_pnl for p in positions), default=Decimal('0')),
            total_volume=sum(p.market_value for p in positions),
            total_fees=Decimal('0')  # Would need fee data
        )
    
    # =========================================================================
    # ALERT MANAGEMENT
    # =========================================================================
    
    async def set_position_alert(
        self,
        position_id: str,
        alert_type: str,
        threshold: Decimal,
        severity: str = "warning",
        message: Optional[str] = None
    ) -> PositionAlert:
        """
        Set an alert for a position.
        
        Args:
            position_id: Position ID
            alert_type: Alert type ('price', 'pnl', 'drawdown', 'time')
            threshold: Alert threshold
            severity: Alert severity
            message: Alert message
            
        Returns:
            PositionAlert
        """
        position = await self.get_position(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")
        
        alert = PositionAlert(
            position_id=position_id,
            type=alert_type,
            severity=severity,
            message=message or f"{alert_type} alert triggered",
            value=Decimal('0'),
            threshold=threshold
        )
        
        self._alerts.append(alert)
        
        return alert
    
    async def _check_alerts(self, position: Position):
        """
        Check alerts for a position.
        
        Args:
            position: Position to check
        """
        for alert in self._alerts:
            if alert.position_id != position.id or alert.acknowledged:
                continue
            
            triggered = False
            
            if alert.type == 'price':
                if position.current_price <= alert.threshold:
                    triggered = True
            elif alert.type == 'pnl':
                if position.total_pnl <= alert.threshold:
                    triggered = True
            elif alert.type == 'drawdown':
                if position.unrealized_pnl <= alert.threshold:
                    triggered = True
            elif alert.type == 'time':
                days = (datetime.utcnow() - position.opened_at).total_seconds() / 86400
                if days >= float(alert.threshold):
                    triggered = True
            
            if triggered:
                alert.value = position.current_price if alert.type == 'price' else position.total_pnl
                await self._trigger_callbacks("position_alert", alert)
    
    # =========================================================================
    # EXIT CONDITIONS
    # =========================================================================
    
    async def _check_exit_conditions(self, position: Position):
        """
        Check exit conditions for a position.
        
        Args:
            position: Position to check
        """
        # Stop loss
        if position.stop_loss:
            if position.side == PositionSide.LONG and position.current_price <= position.stop_loss:
                await self.close_position(position.id, PositionExitReason.STOP_LOSS)
                return
            elif position.side == PositionSide.SHORT and position.current_price >= position.stop_loss:
                await self.close_position(position.id, PositionExitReason.STOP_LOSS)
                return
        
        # Take profit
        if position.take_profit:
            if position.side == PositionSide.LONG and position.current_price >= position.take_profit:
                await self.close_position(position.id, PositionExitReason.TARGET_REACHED)
                return
            elif position.side == PositionSide.SHORT and position.current_price <= position.take_profit:
                await self.close_position(position.id, PositionExitReason.TARGET_REACHED)
                return
        
        # Trailing stop
        if position.trailing_stop:
            if position.side == PositionSide.LONG:
                # Track highest price
                pass
            elif position.side == PositionSide.SHORT:
                # Track lowest price
                pass
    
    # =========================================================================
    # UPDATE LOOP
    # =========================================================================
    
    async def _update_loop(self):
        """Periodic update loop."""
        while self._running:
            try:
                await asyncio.sleep(5)  # Every 5 seconds
                
                # Update all open positions
                for position in await self.get_open_positions():
                    try:
                        # Get latest prices
                        price_updates = {}
                        for leg in position.legs:
                            price = await self.market_data.get_price(leg.exchange, leg.symbol)
                            price_updates[leg.symbol] = price.last
                        
                        # Update position
                        await self.update_position(
                            position_id=position.id,
                            price_updates=price_updates
                        )
                        
                    except Exception as e:
                        logger.error(f"Error updating position {position.id}: {e}")
                
                # Save position history
                if self.pool:
                    for position in self._positions.values():
                        if position.is_open:
                            await self._save_history(position)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(10)
    
    # =========================================================================
    # CALLBACKS
    # =========================================================================
    
    async def on(self, event: str, callback: Callable):
        """
        Register a callback for an event.
        
        Args:
            event: Event name
            callback: Callback function
        """
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    async def _trigger_callbacks(self, event: str, data: Any):
        """
        Trigger callbacks for an event.
        
        Args:
            event: Event name
            data: Event data
        """
        if event not in self._callbacks:
            return
        
        for callback in self._callbacks[event]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_positions(self):
        """Load positions from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM tracker_positions WHERE status != 'closed'"
                )
                
                for row in rows:
                    # Load legs
                    leg_rows = await conn.fetch(
                        "SELECT * FROM tracker_position_legs WHERE position_id = $1",
                        row['id']
                    )
                    
                    legs = []
                    for leg_row in leg_rows:
                        leg = PositionLeg(
                            id=leg_row['id'],
                            exchange=leg_row['exchange'],
                            symbol=leg_row['symbol'],
                            side=PositionSide(leg_row['side']),
                            entry_price=leg_row['entry_price'],
                            current_price=leg_row['current_price'],
                            quantity=leg_row['quantity'],
                            filled_quantity=leg_row['filled_quantity'],
                            status=PositionLegStatus(leg_row['status']),
                            order_id=leg_row['order_id'],
                            entry_time=leg_row['entry_time'],
                            filled_time=leg_row['filled_time'],
                            metadata=leg_row['metadata'] or {}
                        )
                        legs.append(leg)
                    
                    position = Position(
                        id=row['id'],
                        strategy_id=row['strategy_id'],
                        type=PositionType(row['type']),
                        status=PositionStatus(row['status']),
                        legs=legs,
                        total_quantity=row['total_quantity'],
                        average_entry_price=row['avg_entry_price'],
                        current_price=row['current_price'],
                        market_value=row['market_value'],
                        cost_basis=row['cost_basis'],
                        unrealized_pnl=row['unrealized_pnl'],
                        realized_pnl=row['realized_pnl'],
                        total_pnl=row['total_pnl'],
                        pnl_percent=row['pnl_percent'],
                        stop_loss=row['stop_loss'],
                        take_profit=row['take_profit'],
                        trailing_stop=row['trailing_stop'],
                        risk_reward_ratio=row['risk_reward_ratio'],
                        opened_at=row['opened_at'],
                        updated_at=row['updated_at'],
                        closed_at=row['closed_at'],
                        exit_reason=PositionExitReason(row['exit_reason']) if row['exit_reason'] else None,
                        tags=row['tags'] or [],
                        metadata=row['metadata'] or {}
                    )
                    self._positions[position.id] = position
                
                logger.info(f"Loaded {len(self._positions)} positions")
                
        except Exception as e:
            logger.error(f"Error loading positions: {e}")
    
    async def _save_position(self, position: Position):
        """Save position to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tracker_positions (
                        id, strategy_id, type, status,
                        total_quantity, avg_entry_price, current_price,
                        market_value, cost_basis, unrealized_pnl,
                        realized_pnl, total_pnl, pnl_percent,
                        stop_loss, take_profit, trailing_stop,
                        risk_reward_ratio, opened_at, updated_at,
                        closed_at, exit_reason, tags, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16,
                              $17, $18, $19, $20, $21, $22, $23)
                    """,
                    position.id,
                    position.strategy_id,
                    position.type.value,
                    position.status.value,
                    position.total_quantity,
                    position.average_entry_price,
                    position.current_price,
                    position.market_value,
                    position.cost_basis,
                    position.unrealized_pnl,
                    position.realized_pnl,
                    position.total_pnl,
                    position.pnl_percent,
                    position.stop_loss,
                    position.take_profit,
                    position.trailing_stop,
                    position.risk_reward_ratio,
                    position.opened_at,
                    position.updated_at,
                    position.closed_at,
                    position.exit_reason.value if position.exit_reason else None,
                    json.dumps(position.tags),
                    json.dumps(position.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving position: {e}")
    
    async def _update_position(self, position: Position):
        """Update position in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tracker_positions SET
                        status = $1,
                        total_quantity = $2,
                        avg_entry_price = $3,
                        current_price = $4,
                        market_value = $5,
                        cost_basis = $6,
                        unrealized_pnl = $7,
                        realized_pnl = $8,
                        total_pnl = $9,
                        pnl_percent = $10,
                        updated_at = $11,
                        closed_at = $12,
                        exit_reason = $13,
                        metadata = $14
                    WHERE id = $15
                    """,
                    position.status.value,
                    position.total_quantity,
                    position.average_entry_price,
                    position.current_price,
                    position.market_value,
                    position.cost_basis,
                    position.unrealized_pnl,
                    position.realized_pnl,
                    position.total_pnl,
                    position.pnl_percent,
                    position.updated_at,
                    position.closed_at,
                    position.exit_reason.value if position.exit_reason else None,
                    json.dumps(position.metadata, default=str),
                    position.id
                )
        except Exception as e:
            logger.error(f"Error updating position: {e}")
    
    async def _save_leg(self, leg: PositionLeg, position_id: str):
        """Save leg to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tracker_position_legs (
                        id, position_id, exchange, symbol, side,
                        entry_price, current_price, quantity,
                        filled_quantity, status, order_id,
                        entry_time, filled_time, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13, $14)
                    """,
                    leg.id,
                    position_id,
                    leg.exchange,
                    leg.symbol,
                    leg.side.value,
                    leg.entry_price,
                    leg.current_price,
                    leg.quantity,
                    leg.filled_quantity,
                    leg.status.value,
                    leg.order_id,
                    leg.entry_time,
                    leg.filled_time,
                    json.dumps(leg.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving leg: {e}")
    
    async def _update_leg(self, leg: PositionLeg):
        """Update leg in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tracker_position_legs SET
                        current_price = $1,
                        filled_quantity = $2,
                        status = $3,
                        order_id = $4,
                        filled_time = $5,
                        metadata = $6
                    WHERE id = $7
                    """,
                    leg.current_price,
                    leg.filled_quantity,
                    leg.status.value,
                    leg.order_id,
                    leg.filled_time,
                    json.dumps(leg.metadata, default=str),
                    leg.id
                )
        except Exception as e:
            logger.error(f"Error updating leg: {e}")
    
    async def _save_history(self, position: Position):
        """Save position history to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tracker_position_history (
                        position_id, timestamp, status, price, pnl, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    position.id,
                    datetime.utcnow(),
                    position.status.value,
                    position.current_price,
                    position.total_pnl,
                    json.dumps(position.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving history: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the position tracker."""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        logger.info("PositionTracker shutdown")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class CircuitBreakerOpenError(Exception):
    """Circuit breaker open error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PositionTracker',
    'PositionStatus',
    'PositionLegStatus',
    'PositionSide',
    'PositionType',
    'PositionExitReason',
    'PositionLeg',
    'Position',
    'PositionAlert',
    'PositionSummary',
    'CircuitBreakerOpenError'
]
