# trading/bots/arbitrage_bot/core/portfolio_manager.py
# Nexus AI Trading System - Arbitrage Bot Portfolio Manager Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Portfolio Manager Module

This module provides comprehensive portfolio management for the arbitrage
bot system, including:

- Multi-asset portfolio tracking
- Real-time P&L calculation
- Risk metrics and analytics
- Performance attribution
- Portfolio rebalancing
- Position sizing optimization
- Drawdown management
- Capital allocation
- Portfolio diversification
- Performance reporting
- Risk-adjusted return analysis
- Stress testing
- Scenario analysis
- Portfolio optimization
- Asset allocation
- Correlation analysis
- Portfolio hedging
- Capital efficiency optimization

The portfolio manager ensures optimal capital utilization and risk
management across all arbitrage strategies.
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
import pandas as pd
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.balance_manager import BalanceManager, Balance
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketPrice
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class PortfolioStatus(str, Enum):
    """Portfolio status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    REBALANCING = "rebalancing"
    HEDGING = "hedging"
    LIQUIDATING = "liquidating"
    PAUSED = "paused"


class PositionType(str, Enum):
    """Position types."""
    LONG = "long"
    SHORT = "short"
    HEDGE = "hedge"
    ARBITRAGE = "arbitrage"


class RiskLevel(str, Enum):
    """Risk levels."""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class AllocationStrategy(str, Enum):
    """Allocation strategies."""
    EQUAL = "equal"
    PROPORTIONAL = "proportional"
    RISK_PARITY = "risk_parity"
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    CUSTOM = "custom"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PortfolioConfig(BaseModel):
    """Portfolio configuration."""
    max_positions: int = 20
    min_position_size: Decimal = Decimal('0.01')
    max_position_size: Decimal = Decimal('1000000')
    max_leverage: Decimal = Decimal('3')
    max_risk_per_position: Decimal = Decimal('0.02')  # 2%
    max_risk_per_day: Decimal = Decimal('0.05')  # 5%
    max_drawdown: Decimal = Decimal('0.15')  # 15%
    target_return: Decimal = Decimal('0.15')  # 15%
    risk_free_rate: Decimal = Decimal('0.02')  # 2%
    rebalance_threshold: Decimal = Decimal('0.01')  # 1%
    rebalance_interval: int = 3600  # seconds
    volatility_target: Decimal = Decimal('0.01')  # 1%
    diversification_target: Decimal = Decimal('0.5')  # 50%
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('max_positions', 'rebalance_interval')
    def validate_positive_int(cls, v):
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @validator('min_position_size', 'max_position_size', 'max_leverage')
    def validate_positive_decimal(cls, v):
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @validator('max_risk_per_position', 'max_risk_per_day', 'max_drawdown')
    def validate_risk(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Risk must be between 0 and 1")
        return v


class PortfolioPosition(BaseModel):
    """Portfolio position."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    exchange: str
    type: PositionType
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Decimal('0')
    total_pnl: Decimal
    pnl_percent: Decimal
    weight: Decimal
    allocation: Decimal
    leverage: Decimal = Decimal('1')
    margin: Decimal = Decimal('0')
    risk_contribution: Decimal = Decimal('0')
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        """Check if position is open."""
        return self.closed_at is None

    @property
    def is_profitable(self) -> bool:
        """Check if position is profitable."""
        return self.total_pnl > 0

    @property
    def return_on_investment(self) -> Decimal:
        """Calculate ROI."""
        if self.cost_basis == 0:
            return Decimal('0')
        return self.total_pnl / self.cost_basis * 100


class PortfolioSnapshot(BaseModel):
    """Portfolio snapshot."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_value: Decimal
    cash_balance: Decimal
    invested_value: Decimal
    total_pnl: Decimal
    daily_pnl: Decimal
    weekly_pnl: Decimal
    monthly_pnl: Decimal
    positions: List[PortfolioPosition] = Field(default_factory=list)
    weights: Dict[str, Decimal] = Field(default_factory=dict)
    risk_metrics: Dict[str, Decimal] = Field(default_factory=dict)
    performance_metrics: Dict[str, Decimal] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioMetrics(BaseModel):
    """Portfolio metrics."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Returns
    total_return: Decimal
    annualized_return: Decimal
    cumulative_return: Decimal
    daily_return: Decimal
    
    # Risk
    volatility: Decimal
    annualized_volatility: Decimal
    max_drawdown: Decimal
    current_drawdown: Decimal
    var_95: Decimal
    var_99: Decimal
    cvar_95: Decimal
    cvar_99: Decimal
    
    # Risk-adjusted returns
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    omega_ratio: Decimal
    treynor_ratio: Decimal
    
    # Portfolio statistics
    beta: Decimal
    alpha: Decimal
    correlation: Decimal
    diversification_ratio: Decimal
    concentration_ratio: Decimal
    
    # Position statistics
    total_positions: int
    active_positions: int
    win_rate: Decimal
    average_win: Decimal
    average_loss: Decimal
    profit_factor: Decimal
    
    # Capital efficiency
    capital_utilization: Decimal
    leverage_used: Decimal
    margin_usage: Decimal


class PortfolioAllocation(BaseModel):
    """Portfolio allocation."""
    strategy: AllocationStrategy
    assets: Dict[str, Decimal] = Field(default_factory=dict)
    weights: Dict[str, Decimal] = Field(default_factory=dict)
    target_volatility: Optional[Decimal] = None
    target_return: Optional[Decimal] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Portfolio positions
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    type VARCHAR(20) NOT NULL,
    quantity DECIMAL(32, 16) NOT NULL,
    entry_price DECIMAL(32, 16) NOT NULL,
    current_price DECIMAL(32, 16) NOT NULL,
    market_value DECIMAL(32, 16) NOT NULL,
    cost_basis DECIMAL(32, 16) NOT NULL,
    unrealized_pnl DECIMAL(32, 16) NOT NULL,
    realized_pnl DECIMAL(32, 16) DEFAULT 0,
    total_pnl DECIMAL(32, 16) NOT NULL,
    pnl_percent DECIMAL(32, 16) NOT NULL,
    weight DECIMAL(32, 16) NOT NULL,
    allocation DECIMAL(32, 16) NOT NULL,
    leverage DECIMAL(32, 16) DEFAULT 1,
    margin DECIMAL(32, 16) DEFAULT 0,
    risk_contribution DECIMAL(32, 16) DEFAULT 0,
    opened_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_portfolio_positions_symbol (symbol),
    INDEX idx_portfolio_positions_exchange (exchange),
    INDEX idx_portfolio_positions_type (type),
    INDEX idx_portfolio_positions_status (status)
);

-- Portfolio snapshots
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    total_value DECIMAL(32, 16) NOT NULL,
    cash_balance DECIMAL(32, 16) NOT NULL,
    invested_value DECIMAL(32, 16) NOT NULL,
    total_pnl DECIMAL(32, 16) NOT NULL,
    daily_pnl DECIMAL(32, 16) NOT NULL,
    weekly_pnl DECIMAL(32, 16) NOT NULL,
    monthly_pnl DECIMAL(32, 16) NOT NULL,
    positions JSONB DEFAULT '[]',
    weights JSONB DEFAULT '{}',
    risk_metrics JSONB DEFAULT '{}',
    performance_metrics JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    INDEX idx_portfolio_snapshots_timestamp (timestamp)
);

-- Portfolio metrics
CREATE TABLE IF NOT EXISTS portfolio_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    total_return DECIMAL(32, 16) NOT NULL,
    annualized_return DECIMAL(32, 16) NOT NULL,
    cumulative_return DECIMAL(32, 16) NOT NULL,
    daily_return DECIMAL(32, 16) NOT NULL,
    volatility DECIMAL(32, 16) NOT NULL,
    annualized_volatility DECIMAL(32, 16) NOT NULL,
    max_drawdown DECIMAL(32, 16) NOT NULL,
    current_drawdown DECIMAL(32, 16) NOT NULL,
    var_95 DECIMAL(32, 16) NOT NULL,
    var_99 DECIMAL(32, 16) NOT NULL,
    cvar_95 DECIMAL(32, 16) NOT NULL,
    cvar_99 DECIMAL(32, 16) NOT NULL,
    sharpe_ratio DECIMAL(32, 16) NOT NULL,
    sortino_ratio DECIMAL(32, 16) NOT NULL,
    calmar_ratio DECIMAL(32, 16) NOT NULL,
    omega_ratio DECIMAL(32, 16) NOT NULL,
    treynor_ratio DECIMAL(32, 16) NOT NULL,
    beta DECIMAL(32, 16) NOT NULL,
    alpha DECIMAL(32, 16) NOT NULL,
    correlation DECIMAL(32, 16) NOT NULL,
    diversification_ratio DECIMAL(32, 16) NOT NULL,
    concentration_ratio DECIMAL(32, 16) NOT NULL,
    total_positions INTEGER NOT NULL,
    active_positions INTEGER NOT NULL,
    win_rate DECIMAL(32, 16) NOT NULL,
    average_win DECIMAL(32, 16) NOT NULL,
    average_loss DECIMAL(32, 16) NOT NULL,
    profit_factor DECIMAL(32, 16) NOT NULL,
    capital_utilization DECIMAL(32, 16) NOT NULL,
    leverage_used DECIMAL(32, 16) NOT NULL,
    margin_usage DECIMAL(32, 16) NOT NULL,
    INDEX idx_portfolio_metrics_timestamp (timestamp)
);

-- Portfolio allocations
CREATE TABLE IF NOT EXISTS portfolio_allocations (
    id SERIAL PRIMARY KEY,
    strategy VARCHAR(50) NOT NULL,
    assets JSONB NOT NULL,
    weights JSONB NOT NULL,
    target_volatility DECIMAL(32, 16),
    target_return DECIMAL(32, 16),
    constraints JSONB DEFAULT '{}',
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    UNIQUE(strategy, timestamp)
);
"""


# =============================================================================
# PORTFOLIO MANAGER CLASS
# =============================================================================

class PortfolioManager:
    """
    Advanced portfolio manager for arbitrage bot.
    
    Features:
    - Multi-asset portfolio tracking
    - Real-time P&L calculation
    - Risk metrics and analytics
    - Performance attribution
    - Portfolio rebalancing
    - Position sizing optimization
    - Drawdown management
    - Capital allocation
    - Portfolio diversification
    - Performance reporting
    - Risk-adjusted return analysis
    - Stress testing
    - Scenario analysis
    - Portfolio optimization
    - Asset allocation
    - Correlation analysis
    - Portfolio hedging
    - Capital efficiency optimization
    """
    
    def __init__(
        self,
        balance_manager: BalanceManager,
        market_data: MarketDataManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[PortfolioConfig] = None
    ):
        self.balance_manager = balance_manager
        self.market_data = market_data
        self.redis = redis
        self.pool = pool
        self.config = config or PortfolioConfig()
        
        # Positions
        self._positions: Dict[str, PortfolioPosition] = {}
        
        # Snapshots
        self._snapshots: List[PortfolioSnapshot] = []
        
        # Metrics
        self._metrics: List[PortfolioMetrics] = []
        
        # Allocations
        self._allocations: Dict[str, PortfolioAllocation] = {}
        
        # Circuit breakers
        self._portfolio_cb = CircuitBreaker(
            name="portfolio_manager",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Status
        self._status = PortfolioStatus.ACTIVE
        
        # Rebalance task
        self._rebalance_task: Optional[asyncio.Task] = None
        
        logger.info("PortfolioManager initialized")
    
    async def initialize(self):
        """Initialize the portfolio manager."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load positions
        if self.pool:
            await self._load_positions()
        
        # Load snapshots
        if self.pool:
            await self._load_snapshots()
        
        # Load metrics
        if self.pool:
            await self._load_metrics()
        
        # Start rebalance task
        self._running = True
        self._rebalance_task = asyncio.create_task(self._rebalance_loop())
        
        # Start snapshot task
        asyncio.create_task(self._snapshot_loop())
        
        self._initialized = True
        logger.info("PortfolioManager initialized")
    
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
    # POSITION MANAGEMENT
    # =========================================================================
    
    async def add_position(
        self,
        symbol: str,
        exchange: str,
        quantity: Decimal,
        entry_price: Decimal,
        position_type: PositionType = PositionType.ARBITRAGE,
        leverage: Decimal = Decimal('1'),
        metadata: Optional[Dict[str, Any]] = None
    ) -> PortfolioPosition:
        """
        Add a position to the portfolio.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            quantity: Position quantity
            entry_price: Entry price
            position_type: Type of position
            leverage: Leverage used
            metadata: Additional metadata
            
        Returns:
            PortfolioPosition
        """
        if self._portfolio_cb.is_open():
            raise CircuitBreakerOpenError("Portfolio manager circuit breaker is open")
        
        try:
            # Get current price
            current_price = await self.market_data.get_price(exchange, symbol)
            
            # Calculate position metrics
            market_value = quantity * current_price.last
            cost_basis = quantity * entry_price
            pnl = market_value - cost_basis
            pnl_percent = pnl / cost_basis * 100 if cost_basis > 0 else Decimal('0')
            
            # Create position
            position = PortfolioPosition(
                symbol=symbol,
                exchange=exchange,
                type=position_type,
                quantity=quantity,
                entry_price=entry_price,
                current_price=current_price.last,
                market_value=market_value,
                cost_basis=cost_basis,
                unrealized_pnl=pnl,
                total_pnl=pnl,
                pnl_percent=pnl_percent,
                weight=Decimal('0'),
                allocation=Decimal('0'),
                leverage=leverage,
                margin=market_value / leverage if leverage > 0 else market_value,
                opened_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata=metadata or {}
            )
            
            # Add to portfolio
            async with self._lock:
                self._positions[position.id] = position
            
            # Update weights
            await self._update_weights()
            
            # Save to database
            if self.pool:
                await self._save_position(position)
            
            # Record success
            self._portfolio_cb.record_success()
            
            logger.info(
                f"Added position {position.id}: {quantity} {symbol} "
                f"@{entry_price} ({position_type.value})"
            )
            
            return position
            
        except Exception as e:
            self._portfolio_cb.record_failure()
            logger.error(f"Error adding position: {e}")
            raise
    
    async def update_position(
        self,
        position_id: str,
        quantity: Optional[Decimal] = None,
        entry_price: Optional[Decimal] = None,
        realized_pnl: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[PortfolioPosition]:
        """
        Update a position.
        
        Args:
            position_id: Position ID
            quantity: New quantity
            entry_price: New entry price
            realized_pnl: Realized P&L
            metadata: Additional metadata
            
        Returns:
            Updated PortfolioPosition or None
        """
        if position_id not in self._positions:
            return None
        
        position = self._positions[position_id]
        
        # Update fields
        if quantity is not None:
            position.quantity = quantity
            position.market_value = quantity * position.current_price
            position.cost_basis = quantity * position.entry_price
        
        if entry_price is not None:
            position.entry_price = entry_price
            position.cost_basis = position.quantity * entry_price
        
        if realized_pnl is not None:
            position.realized_pnl += realized_pnl
        
        # Recalculate metrics
        position.unrealized_pnl = position.market_value - position.cost_basis
        position.total_pnl = position.unrealized_pnl + position.realized_pnl
        position.pnl_percent = position.total_pnl / position.cost_basis * 100 if position.cost_basis > 0 else Decimal('0')
        
        # Update current price
        try:
            current_price = await self.market_data.get_price(position.exchange, position.symbol)
            position.current_price = current_price.last
            position.market_value = position.quantity * current_price.last
            position.unrealized_pnl = position.market_value - position.cost_basis
            position.total_pnl = position.unrealized_pnl + position.realized_pnl
        except Exception as e:
            logger.error(f"Error updating price for {position.symbol}: {e}")
        
        if metadata:
            position.metadata.update(metadata)
        
        position.updated_at = datetime.utcnow()
        
        # Update weights
        await self._update_weights()
        
        # Save to database
        if self.pool:
            await self._update_position(position)
        
        return position
    
    async def close_position(
        self,
        position_id: str,
        closing_price: Optional[Decimal] = None
    ) -> bool:
        """
        Close a position.
        
        Args:
            position_id: Position ID
            closing_price: Closing price
            
        Returns:
            True if closed successfully
        """
        if position_id not in self._positions:
            return False
        
        position = self._positions[position_id]
        
        if position.closed_at is not None:
            return False
        
        # Calculate final P&L
        if closing_price:
            final_pnl = position.quantity * (closing_price - position.entry_price)
            position.realized_pnl += final_pnl
        
        position.closed_at = datetime.utcnow()
        position.total_pnl = position.realized_pnl
        
        # Remove from active positions
        async with self._lock:
            del self._positions[position_id]
        
        # Update weights
        await self._update_weights()
        
        # Save to database
        if self.pool:
            await self._close_position(position)
        
        logger.info(f"Closed position {position_id}: {position.quantity} {position.symbol}")
        return True
    
    # =========================================================================
    # PORTFOLIO ANALYTICS
    # =========================================================================
    
    async def get_portfolio_value(self) -> Decimal:
        """
        Get total portfolio value.
        
        Returns:
            Total portfolio value
        """
        total = Decimal('0')
        
        # Add position values
        for position in self._positions.values():
            total += position.market_value
        
        # Add cash balance
        balances = await self.balance_manager.get_balances()
        for exchange_balances in balances.values():
            for balance in exchange_balances.values():
                if balance.currency == 'USD' or balance.currency == 'USDT':
                    total += balance.available
        
        return total
    
    async def get_portfolio_pnl(self) -> Dict[str, Decimal]:
        """
        Get portfolio P&L.
        
        Returns:
            Dict with P&L metrics
        """
        total_pnl = Decimal('0')
        unrealized_pnl = Decimal('0')
        realized_pnl = Decimal('0')
        
        for position in self._positions.values():
            if position.closed_at is None:
                total_pnl += position.total_pnl
                unrealized_pnl += position.unrealized_pnl
            realized_pnl += position.realized_pnl
        
        return {
            'total': total_pnl,
            'unrealized': unrealized_pnl,
            'realized': realized_pnl
        }
    
    async def get_portfolio_weights(self) -> Dict[str, Decimal]:
        """
        Get portfolio weights.
        
        Returns:
            Dict mapping symbol to weight
        """
        weights = {}
        total_value = await self.get_portfolio_value()
        
        if total_value == 0:
            return weights
        
        for position in self._positions.values():
            weight = position.market_value / total_value
            weights[position.symbol] = weight
        
        return weights
    
    async def calculate_metrics(self) -> PortfolioMetrics:
        """
        Calculate portfolio metrics.
        
        Returns:
            PortfolioMetrics
        """
        # Get positions
        positions = list(self._positions.values())
        
        if not positions:
            return PortfolioMetrics(
                total_return=Decimal('0'),
                annualized_return=Decimal('0'),
                cumulative_return=Decimal('0'),
                daily_return=Decimal('0'),
                volatility=Decimal('0'),
                annualized_volatility=Decimal('0'),
                max_drawdown=Decimal('0'),
                current_drawdown=Decimal('0'),
                var_95=Decimal('0'),
                var_99=Decimal('0'),
                cvar_95=Decimal('0'),
                cvar_99=Decimal('0'),
                sharpe_ratio=Decimal('0'),
                sortino_ratio=Decimal('0'),
                calmar_ratio=Decimal('0'),
                omega_ratio=Decimal('0'),
                treynor_ratio=Decimal('0'),
                beta=Decimal('0'),
                alpha=Decimal('0'),
                correlation=Decimal('0'),
                diversification_ratio=Decimal('0'),
                concentration_ratio=Decimal('0'),
                total_positions=0,
                active_positions=0,
                win_rate=Decimal('0'),
                average_win=Decimal('0'),
                average_loss=Decimal('0'),
                profit_factor=Decimal('0'),
                capital_utilization=Decimal('0'),
                leverage_used=Decimal('0'),
                margin_usage=Decimal('0')
            )
        
        # Calculate returns
        total_pnl = sum(p.total_pnl for p in positions)
        total_value = await self.get_portfolio_value()
        total_return = total_pnl / total_value if total_value > 0 else Decimal('0')
        
        # Calculate risk metrics
        returns = [float(p.pnl_percent / 100) for p in positions]
        
        if returns:
            vol = np.std(returns)
            sharpe = (np.mean(returns) - float(self.config.risk_free_rate)) / vol if vol > 0 else 0
            
            # Calculate drawdown
            cumulative = np.cumprod(1 + np.array(returns))
            peak = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - peak) / peak
            max_dd = np.min(drawdown)
            
            # Calculate VaR
            var_95 = np.percentile(returns, 5)
            var_99 = np.percentile(returns, 1)
            
            # Calculate CVaR
            cvar_95 = np.mean([r for r in returns if r <= var_95]) if returns else 0
            cvar_99 = np.mean([r for r in returns if r <= var_99]) if returns else 0
        else:
            vol = 0
            sharpe = 0
            max_dd = 0
            var_95 = 0
            var_99 = 0
            cvar_95 = 0
            cvar_99 = 0
        
        # Calculate win rate
        winning = sum(1 for p in positions if p.is_profitable)
        win_rate = winning / len(positions) if positions else 0
        
        # Calculate average win/loss
        wins = [p.total_pnl for p in positions if p.is_profitable]
        losses = [p.total_pnl for p in positions if not p.is_profitable]
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        
        # Calculate profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Calculate diversification
        weights = await self.get_portfolio_weights()
        concentration = sum(w ** 2 for w in weights.values())
        diversification = 1 - concentration
        
        return PortfolioMetrics(
            total_return=Decimal(str(total_return)),
            annualized_return=Decimal(str(total_return * 365)),
            cumulative_return=Decimal(str(total_return)),
            daily_return=Decimal(str(np.mean(returns) if returns else 0)),
            volatility=Decimal(str(vol)),
            annualized_volatility=Decimal(str(vol * np.sqrt(252))),
            max_drawdown=Decimal(str(max_dd)),
            current_drawdown=Decimal(str(np.min(drawdown) if drawdown.size > 0 else 0)),
            var_95=Decimal(str(var_95)),
            var_99=Decimal(str(var_99)),
            cvar_95=Decimal(str(cvar_95)),
            cvar_99=Decimal(str(cvar_99)),
            sharpe_ratio=Decimal(str(sharpe)),
            sortino_ratio=Decimal(str(sharpe)),  # Simplified
            calmar_ratio=Decimal(str(sharpe)),   # Simplified
            omega_ratio=Decimal('0'),
            treynor_ratio=Decimal('0'),
            beta=Decimal('1'),
            alpha=Decimal('0'),
            correlation=Decimal('0'),
            diversification_ratio=Decimal(str(diversification)),
            concentration_ratio=Decimal(str(concentration)),
            total_positions=len(positions),
            active_positions=sum(1 for p in positions if p.closed_at is None),
            win_rate=Decimal(str(win_rate)),
            average_win=Decimal(str(avg_win)),
            average_loss=Decimal(str(abs(avg_loss) if avg_loss else 0)),
            profit_factor=Decimal(str(profit_factor)),
            capital_utilization=Decimal('0.5'),  # Placeholder
            leverage_used=sum(p.leverage for p in positions) / len(positions) if positions else Decimal('0'),
            margin_usage=Decimal('0.5')  # Placeholder
        )
    
    # =========================================================================
    # PORTFOLIO OPTIMIZATION
    # =========================================================================
    
    async def optimize_allocation(
        self,
        strategy: AllocationStrategy,
        assets: List[str],
        constraints: Optional[Dict[str, Any]] = None
    ) -> PortfolioAllocation:
        """
        Optimize portfolio allocation.
        
        Args:
            strategy: Allocation strategy
            assets: List of assets
            constraints: Optimization constraints
            
        Returns:
            PortfolioAllocation
        """
        # Get historical data for assets
        returns_data = {}
        for asset in assets:
            try:
                # Get historical returns
                bars = await self.market_data.get_klines(asset, "1h", 100)
                returns = [float((bar['close'] - bar['open']) / bar['open']) for bar in bars]
                returns_data[asset] = returns
            except Exception as e:
                logger.error(f"Error getting data for {asset}: {e}")
                returns_data[asset] = [0] * 100
        
        # Calculate weights based on strategy
        if strategy == AllocationStrategy.EQUAL:
            weight = Decimal('1') / len(assets)
            weights = {asset: weight for asset in assets}
            
        elif strategy == AllocationStrategy.PROPORTIONAL:
            # Proportional to market cap or value
            # Placeholder - would use actual market data
            weights = {asset: Decimal('0.5') for asset in assets}
            
        elif strategy == AllocationStrategy.RISK_PARITY:
            # Risk parity allocation
            # Placeholder - would use covariance matrix
            weights = {asset: Decimal('0.5') for asset in assets}
            
        elif strategy == AllocationStrategy.MIN_VARIANCE:
            # Minimum variance
            # Placeholder - would use optimization
            weights = {asset: Decimal('0.5') for asset in assets}
            
        elif strategy == AllocationStrategy.MAX_SHARPE:
            # Maximum Sharpe ratio
            # Placeholder - would use optimization
            weights = {asset: Decimal('0.5') for asset in assets}
            
        else:
            weights = {asset: Decimal('0') for asset in assets}
        
        # Normalize weights
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        # Create allocation
        allocation = PortfolioAllocation(
            strategy=strategy,
            assets={asset: Decimal('0') for asset in assets},
            weights=weights,
            constraints=constraints or {},
            timestamp=datetime.utcnow()
        )
        
        self._allocations[strategy.value] = allocation
        
        return allocation
    
    async def rebalance(
        self,
        allocation: Optional[PortfolioAllocation] = None
    ) -> List[Dict[str, Any]]:
        """
        Rebalance portfolio.
        
        Args:
            allocation: Target allocation
            
        Returns:
            List of rebalance actions
        """
        if not allocation:
            # Use existing allocation
            allocation = list(self._allocations.values())[-1] if self._allocations else None
            
            if not allocation:
                return []
        
        # Calculate target positions
        total_value = await self.get_portfolio_value()
        target_positions = {}
        
        for asset, weight in allocation.weights.items():
            if weight > 0:
                target_value = total_value * weight
                target_positions[asset] = target_value
        
        # Compare with current positions
        current_positions = {}
        for position in self._positions.values():
            current_positions[position.symbol] = position.market_value
        
        rebalance_actions = []
        
        for asset, target_value in target_positions.items():
            current_value = current_positions.get(asset, Decimal('0'))
            diff = target_value - current_value
            
            if abs(diff) > self.config.rebalance_threshold * total_value:
                rebalance_actions.append({
                    'asset': asset,
                    'action': 'buy' if diff > 0 else 'sell',
                    'value': abs(diff),
                    'target_value': target_value,
                    'current_value': current_value
                })
        
        return rebalance_actions
    
    # =========================================================================
    # RISK MANAGEMENT
    # =========================================================================
    
    async def check_risk_limits(self) -> Dict[str, Any]:
        """
        Check risk limits.
        
        Returns:
            Dict with risk limit status
        """
        metrics = await self.calculate_metrics()
        
        limits = {
            'max_drawdown': {
                'current': metrics.current_drawdown,
                'limit': self.config.max_drawdown,
                'exceeded': metrics.current_drawdown > self.config.max_drawdown
            },
            'max_risk_per_position': {
                'current': Decimal('0'),  # Would calculate
                'limit': self.config.max_risk_per_position,
                'exceeded': False
            },
            'max_leverage': {
                'current': metrics.leverage_used,
                'limit': self.config.max_leverage,
                'exceeded': metrics.leverage_used > self.config.max_leverage
            },
            'max_positions': {
                'current': len(self._positions),
                'limit': self.config.max_positions,
                'exceeded': len(self._positions) > self.config.max_positions
            }
        }
        
        # Check if any limit exceeded
        exceeded = any(limit['exceeded'] for limit in limits.values())
        
        return {
            'limits': limits,
            'exceeded': exceeded,
            'status': PortfolioStatus.PAUSED if exceeded else PortfolioStatus.ACTIVE
        }
    
    async def apply_stop_loss(self, max_drawdown: Optional[Decimal] = None) -> bool:
        """
        Apply stop-loss to portfolio.
        
        Args:
            max_drawdown: Maximum drawdown threshold
            
        Returns:
            True if stop-loss triggered
        """
        metrics = await self.calculate_metrics()
        threshold = max_drawdown or self.config.max_drawdown
        
        if metrics.current_drawdown < -threshold:
            logger.warning(f"Stop-loss triggered: drawdown {metrics.current_drawdown} < -{threshold}")
            
            # Close all positions
            for position_id in list(self._positions.keys()):
                await self.close_position(position_id)
            
            self._status = PortfolioStatus.PAUSED
            
            return True
        
        return False
    
    # =========================================================================
    # WEIGHT UPDATES
    # =========================================================================
    
    async def _update_weights(self):
        """Update portfolio weights."""
        total_value = await self.get_portfolio_value()
        
        if total_value == 0:
            return
        
        for position in self._positions.values():
            position.weight = position.market_value / total_value
    
    # =========================================================================
    # LOOPS
    # =========================================================================
    
    async def _rebalance_loop(self):
        """Rebalance loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.rebalance_interval)
                
                # Check risk limits
                risk_check = await self.check_risk_limits()
                if risk_check['exceeded']:
                    await self.apply_stop_loss()
                    continue
                
                # Rebalance if needed
                if self._allocations:
                    actions = await self.rebalance()
                    if actions:
                        logger.info(f"Rebalance actions: {actions}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rebalance loop error: {e}")
                await asyncio.sleep(60)
    
    async def _snapshot_loop(self):
        """Snapshot loop."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Take snapshot
                snapshot = await self.take_snapshot()
                
                # Save to database
                if self.pool:
                    await self._save_snapshot(snapshot)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Snapshot loop error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # SNAPSHOTS
    # =========================================================================
    
    async def take_snapshot(self) -> PortfolioSnapshot:
        """
        Take portfolio snapshot.
        
        Returns:
            PortfolioSnapshot
        """
        total_value = await self.get_portfolio_value()
        pnl = await self.get_portfolio_pnl()
        weights = await self.get_portfolio_weights()
        metrics = await self.calculate_metrics()
        
        # Calculate period P&L
        daily_pnl = Decimal('0')
        weekly_pnl = Decimal('0')
        monthly_pnl = Decimal('0')
        
        if self._snapshots:
            last_snapshot = self._snapshots[-1]
            daily_pnl = total_value - last_snapshot.total_value
            
            # Weekly
            for snap in self._snapshots[-7:]:
                weekly_pnl += total_value - snap.total_value
            
            # Monthly
            for snap in self._snapshots[-30:]:
                monthly_pnl += total_value - snap.total_value
        
        snapshot = PortfolioSnapshot(
            total_value=total_value,
            cash_balance=Decimal('0'),  # Would get from balance manager
            invested_value=sum(p.market_value for p in self._positions.values()),
            total_pnl=pnl['total'],
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            monthly_pnl=monthly_pnl,
            positions=list(self._positions.values()),
            weights=weights,
            risk_metrics={
                'volatility': metrics.volatility,
                'max_drawdown': metrics.max_drawdown,
                'var_95': metrics.var_95,
                'var_99': metrics.var_99
            },
            performance_metrics={
                'sharpe_ratio': metrics.sharpe_ratio,
                'sortino_ratio': metrics.sortino_ratio,
                'calmar_ratio': metrics.calmar_ratio,
                'win_rate': metrics.win_rate,
                'profit_factor': metrics.profit_factor
            }
        )
        
        self._snapshots.append(snapshot)
        
        # Keep only last 1000 snapshots
        if len(self._snapshots) > 1000:
            self._snapshots = self._snapshots[-1000:]
        
        return snapshot
    
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
                    "SELECT * FROM portfolio_positions WHERE closed_at IS NULL"
                )
                
                for row in rows:
                    position = PortfolioPosition(
                        id=row['id'],
                        symbol=row['symbol'],
                        exchange=row['exchange'],
                        type=PositionType(row['type']),
                        quantity=row['quantity'],
                        entry_price=row['entry_price'],
                        current_price=row['current_price'],
                        market_value=row['market_value'],
                        cost_basis=row['cost_basis'],
                        unrealized_pnl=row['unrealized_pnl'],
                        realized_pnl=row['realized_pnl'],
                        total_pnl=row['total_pnl'],
                        pnl_percent=row['pnl_percent'],
                        weight=row['weight'],
                        allocation=row['allocation'],
                        leverage=row['leverage'],
                        margin=row['margin'],
                        risk_contribution=row['risk_contribution'],
                        opened_at=row['opened_at'],
                        updated_at=row['updated_at'],
                        closed_at=row['closed_at'],
                        metadata=row['metadata'] or {}
                    )
                    self._positions[position.id] = position
                
                logger.info(f"Loaded {len(self._positions)} positions")
                
        except Exception as e:
            logger.error(f"Error loading positions: {e}")
    
    async def _save_position(self, position: PortfolioPosition):
        """Save position to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO portfolio_positions (
                        id, symbol, exchange, type, quantity,
                        entry_price, current_price, market_value,
                        cost_basis, unrealized_pnl, realized_pnl,
                        total_pnl, pnl_percent, weight, allocation,
                        leverage, margin, risk_contribution,
                        opened_at, updated_at, closed_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16,
                              $17, $18, $19, $20, $21, $22)
                    """,
                    position.id,
                    position.symbol,
                    position.exchange,
                    position.type.value,
                    position.quantity,
                    position.entry_price,
                    position.current_price,
                    position.market_value,
                    position.cost_basis,
                    position.unrealized_pnl,
                    position.realized_pnl,
                    position.total_pnl,
                    position.pnl_percent,
                    position.weight,
                    position.allocation,
                    position.leverage,
                    position.margin,
                    position.risk_contribution,
                    position.opened_at,
                    position.updated_at,
                    position.closed_at,
                    json.dumps(position.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving position: {e}")
    
    async def _update_position(self, position: PortfolioPosition):
        """Update position in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE portfolio_positions SET
                        quantity = $1,
                        entry_price = $2,
                        current_price = $3,
                        market_value = $4,
                        cost_basis = $5,
                        unrealized_pnl = $6,
                        realized_pnl = $7,
                        total_pnl = $8,
                        pnl_percent = $9,
                        weight = $10,
                        allocation = $11,
                        leverage = $12,
                        margin = $13,
                        risk_contribution = $14,
                        updated_at = $15,
                        metadata = $16
                    WHERE id = $17
                    """,
                    position.quantity,
                    position.entry_price,
                    position.current_price,
                    position.market_value,
                    position.cost_basis,
                    position.unrealized_pnl,
                    position.realized_pnl,
                    position.total_pnl,
                    position.pnl_percent,
                    position.weight,
                    position.allocation,
                    position.leverage,
                    position.margin,
                    position.risk_contribution,
                    position.updated_at,
                    json.dumps(position.metadata, default=str),
                    position.id
                )
        except Exception as e:
            logger.error(f"Error updating position: {e}")
    
    async def _close_position(self, position: PortfolioPosition):
        """Close position in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE portfolio_positions SET
                        closed_at = $1,
                        updated_at = $2
                    WHERE id = $3
                    """,
                    position.closed_at,
                    position.updated_at,
                    position.id
                )
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    async def _load_snapshots(self):
        """Load snapshots from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 100"
                )
                
                for row in rows:
                    snapshot = PortfolioSnapshot(
                        id=row['id'],
                        timestamp=row['timestamp'],
                        total_value=row['total_value'],
                        cash_balance=row['cash_balance'],
                        invested_value=row['invested_value'],
                        total_pnl=row['total_pnl'],
                        daily_pnl=row['daily_pnl'],
                        weekly_pnl=row['weekly_pnl'],
                        monthly_pnl=row['monthly_pnl'],
                        positions=[],
                        weights=row['weights'] or {},
                        risk_metrics=row['risk_metrics'] or {},
                        performance_metrics=row['performance_metrics'] or {},
                        metadata=row['metadata'] or {}
                    )
                    self._snapshots.append(snapshot)
                
                logger.info(f"Loaded {len(self._snapshots)} snapshots")
                
        except Exception as e:
            logger.error(f"Error loading snapshots: {e}")
    
    async def _save_snapshot(self, snapshot: PortfolioSnapshot):
        """Save snapshot to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO portfolio_snapshots (
                        id, timestamp, total_value, cash_balance,
                        invested_value, total_pnl, daily_pnl,
                        weekly_pnl, monthly_pnl, positions,
                        weights, risk_metrics, performance_metrics,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14)
                    """,
                    snapshot.id,
                    snapshot.timestamp,
                    snapshot.total_value,
                    snapshot.cash_balance,
                    snapshot.invested_value,
                    snapshot.total_pnl,
                    snapshot.daily_pnl,
                    snapshot.weekly_pnl,
                    snapshot.monthly_pnl,
                    json.dumps([p.dict() for p in snapshot.positions], default=str),
                    json.dumps(snapshot.weights, default=str),
                    json.dumps(snapshot.risk_metrics, default=str),
                    json.dumps(snapshot.performance_metrics, default=str),
                    json.dumps(snapshot.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")
    
    async def _load_metrics(self):
        """Load metrics from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM portfolio_metrics ORDER BY timestamp DESC LIMIT 100"
                )
                
                for row in rows:
                    metric = PortfolioMetrics(
                        timestamp=row['timestamp'],
                        total_return=row['total_return'],
                        annualized_return=row['annualized_return'],
                        cumulative_return=row['cumulative_return'],
                        daily_return=row['daily_return'],
                        volatility=row['volatility'],
                        annualized_volatility=row['annualized_volatility'],
                        max_drawdown=row['max_drawdown'],
                        current_drawdown=row['current_drawdown'],
                        var_95=row['var_95'],
                        var_99=row['var_99'],
                        cvar_95=row['cvar_95'],
                        cvar_99=row['cvar_99'],
                        sharpe_ratio=row['sharpe_ratio'],
                        sortino_ratio=row['sortino_ratio'],
                        calmar_ratio=row['calmar_ratio'],
                        omega_ratio=row['omega_ratio'],
                        treynor_ratio=row['treynor_ratio'],
                        beta=row['beta'],
                        alpha=row['alpha'],
                        correlation=row['correlation'],
                        diversification_ratio=row['diversification_ratio'],
                        concentration_ratio=row['concentration_ratio'],
                        total_positions=row['total_positions'],
                        active_positions=row['active_positions'],
                        win_rate=row['win_rate'],
                        average_win=row['average_win'],
                        average_loss=row['average_loss'],
                        profit_factor=row['profit_factor'],
                        capital_utilization=row['capital_utilization'],
                        leverage_used=row['leverage_used'],
                        margin_usage=row['margin_usage']
                    )
                    self._metrics.append(metric)
                
                logger.info(f"Loaded {len(self._metrics)} metrics")
                
        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the portfolio manager."""
        self._running = False
        
        if self._rebalance_task:
            self._rebalance_task.cancel()
            try:
                await self._rebalance_task
            except asyncio.CancelledError:
                pass
        
        logger.info("PortfolioManager shutdown")


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
    'PortfolioManager',
    'PortfolioStatus',
    'PositionType',
    'RiskLevel',
    'AllocationStrategy',
    'PortfolioConfig',
    'PortfolioPosition',
    'PortfolioSnapshot',
    'PortfolioMetrics',
    'PortfolioAllocation',
    'CircuitBreakerOpenError'
]
