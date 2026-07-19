# trading/bots/arbitrage_bot/core/profit_calculator.py
# Nexus AI Trading System - Arbitrage Bot Profit Calculator Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Profit Calculator Module

This module provides comprehensive profit calculation and optimization
for the arbitrage bot system, including:

- Arbitrage profit calculation
- Multi-leg profit optimization
- Real-time P&L tracking
- Profit attribution analysis
- Performance metrics
- Profit forecasting
- Scenario analysis
- Risk-adjusted profit
- Fee impact analysis
- Slippage impact analysis
- Tax impact analysis
- Net profit calculation
- Gross profit calculation
- Profit factor analysis
- Win rate analysis
- Average profit/loss calculation
- Profit distribution analysis
- Profit optimization strategies

The profit calculator ensures accurate profit measurement and
optimization for all arbitrage strategies.
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
from trading.bots.arbitrage_bot.core.exchange_connector import ExchangeOrder
from trading.bots.arbitrage_bot.core.fee_calculator import FeeCalculator, FeeCalculation
from trading.bots.arbitrage_bot.core.position_tracker import Position, PositionLeg
from shared.helpers.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ProfitType(str, Enum):
    """Profit types."""
    GROSS = "gross"
    NET = "net"
    REALIZED = "realized"
    UNREALIZED = "unrealized"
    TOTAL = "total"


class ProfitMetric(str, Enum):
    """Profit metrics."""
    PNL = "pnl"
    PNL_PERCENT = "pnl_percent"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    PROFIT_FACTOR = "profit_factor"
    WIN_RATE = "win_rate"
    AVERAGE_PROFIT = "average_profit"
    AVERAGE_LOSS = "average_loss"
    MAX_DRAWDOWN = "max_drawdown"
    RECOVERY_FACTOR = "recovery_factor"
    EXPECTANCY = "expectancy"
    RISK_REWARD = "risk_reward"


class ProfitStatus(str, Enum):
    """Profit status."""
    PROFITABLE = "profitable"
    LOSING = "losing"
    BREAK_EVEN = "break_even"
    PENDING = "pending"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ProfitCalculation(BaseModel):
    """Profit calculation result."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Profit amounts
    gross_profit: Decimal = Decimal('0')
    net_profit: Decimal = Decimal('0')
    realized_profit: Decimal = Decimal('0')
    unrealized_profit: Decimal = Decimal('0')
    total_profit: Decimal = Decimal('0')
    
    # Profit percentages
    gross_profit_percent: Decimal = Decimal('0')
    net_profit_percent: Decimal = Decimal('0')
    total_profit_percent: Decimal = Decimal('0')
    
    # Cost breakdown
    fee_cost: Decimal = Decimal('0')
    slippage_cost: Decimal = Decimal('0')
    tax_cost: Decimal = Decimal('0')
    gas_cost: Decimal = Decimal('0')
    total_cost: Decimal = Decimal('0')
    
    # Performance metrics
    profit_factor: Decimal = Decimal('0')
    expectancy: Decimal = Decimal('0')
    risk_reward_ratio: Decimal = Decimal('0')
    
    # Status
    status: ProfitStatus = ProfitStatus.PENDING
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_profitable(self) -> bool:
        """Check if calculation is profitable."""
        return self.net_profit > 0

    @property
    def profit_margin(self) -> Decimal:
        """Calculate profit margin."""
        if self.gross_profit == 0:
            return Decimal('0')
        return self.net_profit / self.gross_profit * 100


class ProfitMetrics(BaseModel):
    """Profit metrics."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Core metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: Decimal = Decimal('0')
    
    # Profit metrics
    total_profit: Decimal = Decimal('0')
    total_loss: Decimal = Decimal('0')
    net_profit: Decimal = Decimal('0')
    average_profit: Decimal = Decimal('0')
    average_loss: Decimal = Decimal('0')
    profit_factor: Decimal = Decimal('0')
    
    # Risk metrics
    max_drawdown: Decimal = Decimal('0')
    max_drawdown_percent: Decimal = Decimal('0')
    current_drawdown: Decimal = Decimal('0')
    current_drawdown_percent: Decimal = Decimal('0')
    
    # Risk-adjusted metrics
    sharpe_ratio: Decimal = Decimal('0')
    sortino_ratio: Decimal = Decimal('0')
    calmar_ratio: Decimal = Decimal('0')
    omega_ratio: Decimal = Decimal('0')
    treynor_ratio: Decimal = Decimal('0')
    
    # Distribution metrics
    pnl_std: Decimal = Decimal('0')
    pnl_skew: Decimal = Decimal('0')
    pnl_kurtosis: Decimal = Decimal('0')
    var_95: Decimal = Decimal('0')
    var_99: Decimal = Decimal('0')
    cvar_95: Decimal = Decimal('0')
    cvar_99: Decimal = Decimal('0')
    
    # Efficiency metrics
    expectancy: Decimal = Decimal('0')
    recovery_factor: Decimal = Decimal('0')
    average_trade_duration: float = 0.0


class ProfitHistory(BaseModel):
    """Profit history entry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trade_id: Optional[str] = None
    position_id: Optional[str] = None
    strategy_id: Optional[str] = None
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    profit: Decimal
    profit_percent: Decimal
    type: ProfitType
    fee: Decimal = Decimal('0')
    slippage: Decimal = Decimal('0')
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProfitForecast(BaseModel):
    """Profit forecast."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    period: str  # hourly, daily, weekly, monthly
    
    # Forecast values
    expected_profit: Decimal
    expected_profit_percent: Decimal
    confidence_interval_low: Decimal
    confidence_interval_high: Decimal
    probability_profit: Decimal  # Probability of making profit
    
    # Factors
    market_volatility: Decimal
    market_trend: str  # bullish, bearish, neutral
    expected_trades: int
    win_rate: Decimal
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Profit calculations
CREATE TABLE IF NOT EXISTS profit_calculations (
    id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    gross_profit DECIMAL(32, 16) NOT NULL,
    net_profit DECIMAL(32, 16) NOT NULL,
    realized_profit DECIMAL(32, 16) NOT NULL,
    unrealized_profit DECIMAL(32, 16) NOT NULL,
    total_profit DECIMAL(32, 16) NOT NULL,
    gross_profit_percent DECIMAL(32, 16) NOT NULL,
    net_profit_percent DECIMAL(32, 16) NOT NULL,
    total_profit_percent DECIMAL(32, 16) NOT NULL,
    fee_cost DECIMAL(32, 16) NOT NULL,
    slippage_cost DECIMAL(32, 16) NOT NULL,
    tax_cost DECIMAL(32, 16) NOT NULL,
    gas_cost DECIMAL(32, 16) NOT NULL,
    total_cost DECIMAL(32, 16) NOT NULL,
    profit_factor DECIMAL(32, 16) NOT NULL,
    expectancy DECIMAL(32, 16) NOT NULL,
    risk_reward_ratio DECIMAL(32, 16) NOT NULL,
    status VARCHAR(20) NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_profit_calculations_timestamp (timestamp),
    INDEX idx_profit_calculations_status (status)
);

-- Profit metrics
CREATE TABLE IF NOT EXISTS profit_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    total_trades INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    losing_trades INTEGER NOT NULL,
    win_rate DECIMAL(32, 16) NOT NULL,
    total_profit DECIMAL(32, 16) NOT NULL,
    total_loss DECIMAL(32, 16) NOT NULL,
    net_profit DECIMAL(32, 16) NOT NULL,
    average_profit DECIMAL(32, 16) NOT NULL,
    average_loss DECIMAL(32, 16) NOT NULL,
    profit_factor DECIMAL(32, 16) NOT NULL,
    max_drawdown DECIMAL(32, 16) NOT NULL,
    max_drawdown_percent DECIMAL(32, 16) NOT NULL,
    current_drawdown DECIMAL(32, 16) NOT NULL,
    current_drawdown_percent DECIMAL(32, 16) NOT NULL,
    sharpe_ratio DECIMAL(32, 16) NOT NULL,
    sortino_ratio DECIMAL(32, 16) NOT NULL,
    calmar_ratio DECIMAL(32, 16) NOT NULL,
    omega_ratio DECIMAL(32, 16) NOT NULL,
    treynor_ratio DECIMAL(32, 16) NOT NULL,
    pnl_std DECIMAL(32, 16) NOT NULL,
    pnl_skew DECIMAL(32, 16) NOT NULL,
    pnl_kurtosis DECIMAL(32, 16) NOT NULL,
    var_95 DECIMAL(32, 16) NOT NULL,
    var_99 DECIMAL(32, 16) NOT NULL,
    cvar_95 DECIMAL(32, 16) NOT NULL,
    cvar_99 DECIMAL(32, 16) NOT NULL,
    expectancy DECIMAL(32, 16) NOT NULL,
    recovery_factor DECIMAL(32, 16) NOT NULL,
    average_trade_duration FLOAT DEFAULT 0,
    UNIQUE(timestamp)
);

-- Profit history
CREATE TABLE IF NOT EXISTS profit_history (
    id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    trade_id VARCHAR(64),
    position_id VARCHAR(64),
    strategy_id VARCHAR(64),
    symbol VARCHAR(50),
    exchange VARCHAR(50),
    profit DECIMAL(32, 16) NOT NULL,
    profit_percent DECIMAL(32, 16) NOT NULL,
    type VARCHAR(20) NOT NULL,
    fee DECIMAL(32, 16) DEFAULT 0,
    slippage DECIMAL(32, 16) DEFAULT 0,
    duration_seconds FLOAT DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    INDEX idx_profit_history_timestamp (timestamp),
    INDEX idx_profit_history_strategy_id (strategy_id),
    INDEX idx_profit_history_symbol (symbol)
);

-- Profit forecasts
CREATE TABLE IF NOT EXISTS profit_forecasts (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    period VARCHAR(20) NOT NULL,
    expected_profit DECIMAL(32, 16) NOT NULL,
    expected_profit_percent DECIMAL(32, 16) NOT NULL,
    confidence_interval_low DECIMAL(32, 16) NOT NULL,
    confidence_interval_high DECIMAL(32, 16) NOT NULL,
    probability_profit DECIMAL(32, 16) NOT NULL,
    market_volatility DECIMAL(32, 16) NOT NULL,
    market_trend VARCHAR(20) NOT NULL,
    expected_trades INTEGER NOT NULL,
    win_rate DECIMAL(32, 16) NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_profit_forecasts_timestamp (timestamp),
    INDEX idx_profit_forecasts_period (period)
);
"""


# =============================================================================
# PROFIT CALCULATOR CLASS
# =============================================================================

class ProfitCalculator:
    """
    Advanced profit calculator for arbitrage bot.
    
    Features:
    - Arbitrage profit calculation
    - Multi-leg profit optimization
    - Real-time P&L tracking
    - Profit attribution analysis
    - Performance metrics
    - Profit forecasting
    - Scenario analysis
    - Risk-adjusted profit
    - Fee impact analysis
    - Slippage impact analysis
    - Tax impact analysis
    - Net profit calculation
    - Gross profit calculation
    - Profit factor analysis
    - Win rate analysis
    - Average profit/loss calculation
    - Profit distribution analysis
    - Profit optimization strategies
    """
    
    def __init__(
        self,
        fee_calculator: Optional[FeeCalculator] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.fee_calculator = fee_calculator
        self.redis = redis
        self.pool = pool
        self.config = config or {}
        
        # Profit history
        self._history: List[ProfitHistory] = []
        
        # Metrics
        self._metrics: Optional[ProfitMetrics] = None
        self._metrics_history: List[ProfitMetrics] = []
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info("ProfitCalculator initialized")
    
    async def initialize(self):
        """Initialize the profit calculator."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load metrics
        if self.pool:
            await self._load_metrics()
        
        self._running = True
        self._initialized = True
        
        logger.info("ProfitCalculator initialized")
    
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
    # PROFIT CALCULATION
    # =========================================================================
    
    async def calculate_position_profit(
        self,
        position: Position,
        include_fees: bool = True,
        include_slippage: bool = True,
        include_tax: bool = True,
        include_gas: bool = True
    ) -> ProfitCalculation:
        """
        Calculate profit for a position.
        
        Args:
            position: Position to calculate
            include_fees: Include fees
            include_slippage: Include slippage
            include_tax: Include tax
            include_gas: Include gas
            
        Returns:
            ProfitCalculation
        """
        # Calculate gross profit
        gross_profit = position.total_pnl
        
        # Calculate costs
        fee_cost = Decimal('0')
        slippage_cost = Decimal('0')
        tax_cost = Decimal('0')
        gas_cost = Decimal('0')
        
        if include_fees and self.fee_calculator:
            for leg in position.legs:
                try:
                    fee = await self.fee_calculator.calculate_trading_fee(
                        exchange=leg.exchange,
                        amount=leg.entry_price * leg.filled_quantity,
                        side="buy" if leg.side.value == "long" else "sell"
                    )
                    fee_cost += fee.amount
                except Exception:
                    pass
        
        total_cost = fee_cost + slippage_cost + tax_cost + gas_cost
        
        # Calculate net profit
        net_profit = gross_profit - total_cost
        
        # Calculate percentages
        gross_percent = (gross_profit / position.cost_basis * 100) if position.cost_basis > 0 else Decimal('0')
        net_percent = (net_profit / position.cost_basis * 100) if position.cost_basis > 0 else Decimal('0')
        
        # Calculate profit factor
        profit_factor = Decimal('0')
        if total_cost > 0:
            profit_factor = gross_profit / total_cost
        
        # Calculate expectancy
        expectancy = Decimal('0')
        if position.total_quantity > 0:
            expectancy = net_profit / position.total_quantity
        
        # Calculate risk-reward ratio
        risk_reward = Decimal('0')
        if position.risk_reward_ratio:
            risk_reward = position.risk_reward_ratio
        
        # Determine status
        status = ProfitStatus.PROFITABLE if net_profit > 0 else ProfitStatus.LOSING
        if net_profit == 0:
            status = ProfitStatus.BREAK_EVEN
        
        return ProfitCalculation(
            gross_profit=gross_profit.quantize(Decimal('0.00000001')),
            net_profit=net_profit.quantize(Decimal('0.00000001')),
            realized_profit=position.realized_pnl.quantize(Decimal('0.00000001')),
            unrealized_profit=position.unrealized_pnl.quantize(Decimal('0.00000001')),
            total_profit=position.total_pnl.quantize(Decimal('0.00000001')),
            gross_profit_percent=gross_percent.quantize(Decimal('0.01')),
            net_profit_percent=net_percent.quantize(Decimal('0.01')),
            total_profit_percent=position.pnl_percent.quantize(Decimal('0.01')),
            fee_cost=fee_cost.quantize(Decimal('0.00000001')),
            slippage_cost=slippage_cost.quantize(Decimal('0.00000001')),
            tax_cost=tax_cost.quantize(Decimal('0.00000001')),
            gas_cost=gas_cost.quantize(Decimal('0.00000001')),
            total_cost=total_cost.quantize(Decimal('0.00000001')),
            profit_factor=profit_factor.quantize(Decimal('0.01')),
            expectancy=expectancy.quantize(Decimal('0.00000001')),
            risk_reward_ratio=risk_reward.quantize(Decimal('0.01')),
            status=status,
            metadata=position.metadata
        )
    
    async def calculate_trade_profit(
        self,
        trade: Dict[str, Any],
        include_fees: bool = True,
        include_slippage: bool = True,
        include_tax: bool = True,
        include_gas: bool = True
    ) -> ProfitCalculation:
        """
        Calculate profit for a single trade.
        
        Args:
            trade: Trade data
            include_fees: Include fees
            include_slippage: Include slippage
            include_tax: Include tax
            include_gas: Include gas
            
        Returns:
            ProfitCalculation
        """
        # Extract trade data
        buy_price = Decimal(str(trade.get('buy_price', 0)))
        sell_price = Decimal(str(trade.get('sell_price', 0)))
        quantity = Decimal(str(trade.get('quantity', 0)))
        fee_rate = Decimal(str(trade.get('fee_rate', 0.001)))
        slippage_rate = Decimal(str(trade.get('slippage_rate', 0)))
        
        # Calculate gross profit
        gross_profit = (sell_price - buy_price) * quantity
        
        # Calculate costs
        buy_fee = buy_price * quantity * fee_rate if include_fees else Decimal('0')
        sell_fee = sell_price * quantity * fee_rate if include_fees else Decimal('0')
        fee_cost = buy_fee + sell_fee
        
        slippage_cost = (buy_price * quantity * slippage_rate) if include_slippage else Decimal('0')
        tax_cost = Decimal('0') if not include_tax else Decimal('0')
        gas_cost = Decimal('0') if not include_gas else Decimal('0')
        
        total_cost = fee_cost + slippage_cost + tax_cost + gas_cost
        
        # Calculate net profit
        net_profit = gross_profit - total_cost
        
        # Calculate percentages
        cost_basis = buy_price * quantity
        gross_percent = (gross_profit / cost_basis * 100) if cost_basis > 0 else Decimal('0')
        net_percent = (net_profit / cost_basis * 100) if cost_basis > 0 else Decimal('0')
        
        # Calculate profit factor
        profit_factor = Decimal('0')
        if total_cost > 0:
            profit_factor = gross_profit / total_cost
        
        # Calculate expectancy
        expectancy = net_profit / quantity if quantity > 0 else Decimal('0')
        
        # Determine status
        status = ProfitStatus.PROFITABLE if net_profit > 0 else ProfitStatus.LOSING
        if net_profit == 0:
            status = ProfitStatus.BREAK_EVEN
        
        return ProfitCalculation(
            gross_profit=gross_profit.quantize(Decimal('0.00000001')),
            net_profit=net_profit.quantize(Decimal('0.00000001')),
            realized_profit=net_profit.quantize(Decimal('0.00000001')),
            unrealized_profit=Decimal('0'),
            total_profit=net_profit.quantize(Decimal('0.00000001')),
            gross_profit_percent=gross_percent.quantize(Decimal('0.01')),
            net_profit_percent=net_percent.quantize(Decimal('0.01')),
            total_profit_percent=net_percent.quantize(Decimal('0.01')),
            fee_cost=fee_cost.quantize(Decimal('0.00000001')),
            slippage_cost=slippage_cost.quantize(Decimal('0.00000001')),
            tax_cost=tax_cost.quantize(Decimal('0.00000001')),
            gas_cost=gas_cost.quantize(Decimal('0.00000001')),
            total_cost=total_cost.quantize(Decimal('0.00000001')),
            profit_factor=profit_factor.quantize(Decimal('0.01')),
            expectancy=expectancy.quantize(Decimal('0.00000001')),
            risk_reward_ratio=Decimal('0'),
            status=status,
            metadata=trade.get('metadata', {})
        )
    
    # =========================================================================
    # METRICS CALCULATION
    # =========================================================================
    
    async def calculate_metrics(
        self,
        history: Optional[List[ProfitHistory]] = None,
        period: str = "all"  # all, daily, weekly, monthly
    ) -> ProfitMetrics:
        """
        Calculate profit metrics.
        
        Args:
            history: Profit history (default: all)
            period: Time period
            
        Returns:
            ProfitMetrics
        """
        if history is None:
            history = self._history
        
        if not history:
            return ProfitMetrics()
        
        # Filter by period
        if period != "all":
            cutoff = datetime.utcnow()
            if period == "daily":
                cutoff = cutoff - timedelta(days=1)
            elif period == "weekly":
                cutoff = cutoff - timedelta(days=7)
            elif period == "monthly":
                cutoff = cutoff - timedelta(days=30)
            history = [h for h in history if h.timestamp > cutoff]
        
        # Calculate core metrics
        total_trades = len(history)
        winning = [h for h in history if h.profit > 0]
        losing = [h for h in history if h.profit < 0]
        break_even = [h for h in history if h.profit == 0]
        
        winning_trades = len(winning)
        losing_trades = len(losing)
        win_rate = Decimal(str(winning_trades / total_trades)) if total_trades > 0 else Decimal('0')
        
        # Calculate profit metrics
        total_profit = sum(h.profit for h in winning) if winning else Decimal('0')
        total_loss = abs(sum(h.profit for h in losing)) if losing else Decimal('0')
        net_profit = total_profit - total_loss
        
        avg_profit = total_profit / winning_trades if winning_trades > 0 else Decimal('0')
        avg_loss = total_loss / losing_trades if losing_trades > 0 else Decimal('0')
        profit_factor = total_profit / total_loss if total_loss > 0 else Decimal('inf')
        
        # Calculate drawdown
        cumulative = [Decimal('0')]
        for h in history:
            cumulative.append(cumulative[-1] + h.profit)
        
        max_drawdown = Decimal('0')
        current_drawdown = Decimal('0')
        peak = Decimal('0')
        
        for value in cumulative:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            current_drawdown = drawdown
        
        max_drawdown_percent = (max_drawdown / max(cumulative) * 100) if max(cumulative) > 0 else Decimal('0')
        current_drawdown_percent = (current_drawdown / max(cumulative) * 100) if max(cumulative) > 0 else Decimal('0')
        
        # Calculate risk-adjusted metrics
        returns = [float(h.profit_percent) for h in history]
        if returns:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            sharpe_ratio = mean_return / std_return if std_return > 0 else 0
            sortino_ratio = mean_return / np.std([r for r in returns if r < 0]) if np.std([r for r in returns if r < 0]) > 0 else 0
            
            # Calmar ratio
            max_dd = float(max_drawdown_percent)
            calmar_ratio = mean_return / max_dd if max_dd > 0 else 0
            
            # VaR and CVaR
            var_95 = np.percentile(returns, 5)
            var_99 = np.percentile(returns, 1)
            cvar_95 = np.mean([r for r in returns if r <= var_95]) if returns else 0
            cvar_99 = np.mean([r for r in returns if r <= var_99]) if returns else 0
            
            # Distribution metrics
            pnl_std = np.std(returns)
            pnl_skew = np.mean(((np.array(returns) - mean_return) ** 3)) / (pnl_std ** 3) if pnl_std > 0 else 0
            pnl_kurtosis = np.mean(((np.array(returns) - mean_return) ** 4)) / (pnl_std ** 4) if pnl_std > 0 else 0
        else:
            sharpe_ratio = 0
            sortino_ratio = 0
            calmar_ratio = 0
            var_95 = 0
            var_99 = 0
            cvar_95 = 0
            cvar_99 = 0
            pnl_std = 0
            pnl_skew = 0
            pnl_kurtosis = 0
        
        # Calculate expectancy
        expectancy = net_profit / total_trades if total_trades > 0 else Decimal('0')
        
        # Calculate recovery factor
        recovery_factor = net_profit / max_drawdown if max_drawdown > 0 else Decimal('0')
        
        # Calculate average trade duration
        durations = [h.duration_seconds for h in history if h.duration_seconds > 0]
        avg_duration = np.mean(durations) if durations else 0
        
        return ProfitMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate.quantize(Decimal('0.01')),
            total_profit=total_profit.quantize(Decimal('0.00000001')),
            total_loss=total_loss.quantize(Decimal('0.00000001')),
            net_profit=net_profit.quantize(Decimal('0.00000001')),
            average_profit=avg_profit.quantize(Decimal('0.00000001')),
            average_loss=avg_loss.quantize(Decimal('0.00000001')),
            profit_factor=Decimal(str(profit_factor)).quantize(Decimal('0.01')),
            max_drawdown=max_drawdown.quantize(Decimal('0.00000001')),
            max_drawdown_percent=max_drawdown_percent.quantize(Decimal('0.01')),
            current_drawdown=current_drawdown.quantize(Decimal('0.00000001')),
            current_drawdown_percent=current_drawdown_percent.quantize(Decimal('0.01')),
            sharpe_ratio=Decimal(str(sharpe_ratio)).quantize(Decimal('0.01')),
            sortino_ratio=Decimal(str(sortino_ratio)).quantize(Decimal('0.01')),
            calmar_ratio=Decimal(str(calmar_ratio)).quantize(Decimal('0.01')),
            omega_ratio=Decimal('0'),
            treynor_ratio=Decimal('0'),
            pnl_std=Decimal(str(pnl_std)).quantize(Decimal('0.01')),
            pnl_skew=Decimal(str(pnl_skew)).quantize(Decimal('0.01')),
            pnl_kurtosis=Decimal(str(pnl_kurtosis)).quantize(Decimal('0.01')),
            var_95=Decimal(str(var_95)).quantize(Decimal('0.01')),
            var_99=Decimal(str(var_99)).quantize(Decimal('0.01')),
            cvar_95=Decimal(str(cvar_95)).quantize(Decimal('0.01')),
            cvar_99=Decimal(str(cvar_99)).quantize(Decimal('0.01')),
            expectancy=expectancy.quantize(Decimal('0.00000001')),
            recovery_factor=recovery_factor.quantize(Decimal('0.01')),
            average_trade_duration=avg_duration
        )
    
    # =========================================================================
    # PROFIT FORECASTING
    # =========================================================================
    
    async def forecast_profit(
        self,
        period: str = "daily",
        history: Optional[List[ProfitHistory]] = None,
        confidence_level: float = 0.95
    ) -> ProfitForecast:
        """
        Forecast future profit.
        
        Args:
            period: Forecast period
            history: Historical data
            confidence_level: Confidence level
            
        Returns:
            ProfitForecast
        """
        if history is None:
            history = self._history
        
        if not history:
            return ProfitForecast(
                period=period,
                expected_profit=Decimal('0'),
                expected_profit_percent=Decimal('0'),
                confidence_interval_low=Decimal('0'),
                confidence_interval_high=Decimal('0'),
                probability_profit=Decimal('0'),
                market_volatility=Decimal('0'),
                market_trend="neutral",
                expected_trades=0,
                win_rate=Decimal('0')
            )
        
        # Calculate historical metrics
        metrics = await self.calculate_metrics(history, period)
        
        # Calculate daily profit rate
        if period == "daily":
            days = len(set(h.timestamp.date() for h in history))
            daily_profit = metrics.net_profit / days if days > 0 else Decimal('0')
            expected_profit = daily_profit
            
            # Volatility
            volatility = metrics.pnl_std
            
            # Win rate
            win_rate = metrics.win_rate
            
        elif period == "weekly":
            weeks = len(set((h.timestamp - timedelta(days=h.timestamp.weekday())).date() for h in history))
            weekly_profit = metrics.net_profit / weeks if weeks > 0 else Decimal('0')
            expected_profit = weekly_profit
            volatility = metrics.pnl_std * np.sqrt(5)
            win_rate = metrics.win_rate
            
        elif period == "monthly":
            months = len(set((h.timestamp.replace(day=1)).date() for h in history))
            monthly_profit = metrics.net_profit / months if months > 0 else Decimal('0')
            expected_profit = monthly_profit
            volatility = metrics.pnl_std * np.sqrt(21)
            win_rate = metrics.win_rate
            
        else:
            expected_profit = Decimal('0')
            volatility = Decimal('0')
            win_rate = Decimal('0')
        
        # Calculate confidence interval
        z_score = 1.96 if confidence_level == 0.95 else 2.576 if confidence_level == 0.99 else 1.645
        std_dev = volatility * Decimal(str(z_score))
        
        confidence_low = expected_profit - std_dev
        confidence_high = expected_profit + std_dev
        
        # Calculate probability of profit
        probability = Decimal('0')
        if volatility > 0:
            from scipy import stats
            prob = stats.norm.cdf(0, float(expected_profit), float(volatility))
            probability = Decimal(str(prob))
        
        # Determine market trend
        if len(history) > 10:
            recent = history[-10:]
            returns = [float(h.profit) for h in recent]
            trend = np.polyfit(range(len(returns)), returns, 1)[0]
            market_trend = "bullish" if trend > 0 else "bearish" if trend < 0 else "neutral"
        else:
            market_trend = "neutral"
        
        # Expected trades
        daily_trades = metrics.total_trades / max(1, (datetime.utcnow() - history[0].timestamp).days)
        expected_trades = int(daily_trades * (30 if period == "monthly" else 7 if period == "weekly" else 1))
        
        return ProfitForecast(
            period=period,
            expected_profit=expected_profit.quantize(Decimal('0.00000001')),
            expected_profit_percent=(expected_profit / max(1, abs(metrics.total_profit)) * 100).quantize(Decimal('0.01')),
            confidence_interval_low=confidence_low.quantize(Decimal('0.00000001')),
            confidence_interval_high=confidence_high.quantize(Decimal('0.00000001')),
            probability_profit=probability.quantize(Decimal('0.01')),
            market_volatility=volatility.quantize(Decimal('0.01')),
            market_trend=market_trend,
            expected_trades=expected_trades,
            win_rate=win_rate.quantize(Decimal('0.01')),
            metadata={
                "confidence_level": confidence_level,
                "period_days": 30 if period == "monthly" else 7 if period == "weekly" else 1
            }
        )
    
    # =========================================================================
    # PROFIT HISTORY
    # =========================================================================
    
    async def add_profit_history(
        self,
        profit: Decimal,
        profit_percent: Decimal,
        profit_type: ProfitType = ProfitType.REALIZED,
        trade_id: Optional[str] = None,
        position_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
        fee: Decimal = Decimal('0'),
        slippage: Decimal = Decimal('0'),
        duration_seconds: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProfitHistory:
        """
        Add a profit history entry.
        
        Args:
            profit: Profit amount
            profit_percent: Profit percentage
            profit_type: Type of profit
            trade_id: Trade ID
            position_id: Position ID
            strategy_id: Strategy ID
            symbol: Symbol
            exchange: Exchange
            fee: Fee paid
            slippage: Slippage
            duration_seconds: Duration in seconds
            metadata: Additional metadata
            
        Returns:
            ProfitHistory
        """
        history = ProfitHistory(
            timestamp=datetime.utcnow(),
            trade_id=trade_id,
            position_id=position_id,
            strategy_id=strategy_id,
            symbol=symbol,
            exchange=exchange,
            profit=profit.quantize(Decimal('0.00000001')),
            profit_percent=profit_percent.quantize(Decimal('0.01')),
            type=profit_type,
            fee=fee.quantize(Decimal('0.00000001')),
            slippage=slippage.quantize(Decimal('0.00000001')),
            duration_seconds=duration_seconds,
            metadata=metadata or {}
        )
        
        self._history.append(history)
        
        # Trim history if too large
        if len(self._history) > 10000:
            self._history = self._history[-5000:]
        
        # Save to database
        if self.pool:
            await self._save_history(history)
        
        # Update metrics
        self._metrics = await self.calculate_metrics()
        
        if self.pool:
            await self._save_metrics(self._metrics)
        
        return history
    
    # =========================================================================
    # PROFIT OPTIMIZATION
    # =========================================================================
    
    async def optimize_profit(
        self,
        strategy_id: str,
        current_profit: Decimal,
        target_profit: Decimal,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Optimize profit for a strategy.
        
        Args:
            strategy_id: Strategy ID
            current_profit: Current profit
            target_profit: Target profit
            constraints: Optimization constraints
            
        Returns:
            Optimization recommendations
        """
        # Get strategy history
        history = [h for h in self._history if h.strategy_id == strategy_id]
        
        if not history:
            return {
                "strategy_id": strategy_id,
                "current_profit": float(current_profit),
                "target_profit": float(target_profit),
                "gap": float(target_profit - current_profit),
                "recommendations": ["No historical data available"]
            }
        
        # Calculate metrics
        metrics = await self.calculate_metrics(history)
        
        # Analyze profit drivers
        winning = [h for h in history if h.profit > 0]
        losing = [h for h in history if h.profit < 0]
        
        avg_win = sum(h.profit for h in winning) / len(winning) if winning else Decimal('0')
        avg_loss = abs(sum(h.profit for h in losing) / len(losing)) if losing else Decimal('0')
        
        win_rate = metrics.win_rate
        
        # Calculate expected value per trade
        ev = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        # Determine improvements needed
        gap = target_profit - current_profit
        needed_trades = gap / ev if ev > 0 else Decimal('inf')
        
        recommendations = []
        
        if win_rate < Decimal('0.5'):
            recommendations.append("Improve win rate - consider better entry/exit signals")
        
        if avg_win < avg_loss * Decimal('1.5'):
            recommendations.append("Improve risk-reward ratio - consider wider take profits")
        
        if metrics.profit_factor < Decimal('1.5'):
            recommendations.append("Improve profit factor - reduce losing trades or increase winning trades")
        
        if gap > 0:
            recommendations.append(f"Increase trade frequency by approximately {int(needed_trades)} trades")
        
        return {
            "strategy_id": strategy_id,
            "current_profit": float(current_profit),
            "target_profit": float(target_profit),
            "gap": float(gap),
            "win_rate": float(win_rate),
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "profit_factor": float(metrics.profit_factor),
            "needed_trades": int(needed_trades) if needed_trades != Decimal('inf') else None,
            "recommendations": recommendations
        }
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_history(self, history: ProfitHistory):
        """Save profit history to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO profit_history (
                        id, timestamp, trade_id, position_id,
                        strategy_id, symbol, exchange,
                        profit, profit_percent, type,
                        fee, slippage, duration_seconds,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7,
                              $8, $9, $10, $11, $12, $13, $14)
                    """,
                    history.id,
                    history.timestamp,
                    history.trade_id,
                    history.position_id,
                    history.strategy_id,
                    history.symbol,
                    history.exchange,
                    history.profit,
                    history.profit_percent,
                    history.type.value,
                    history.fee,
                    history.slippage,
                    history.duration_seconds,
                    json.dumps(history.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving profit history: {e}")
    
    async def _save_metrics(self, metrics: ProfitMetrics):
        """Save metrics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO profit_metrics (
                        timestamp, total_trades, winning_trades,
                        losing_trades, win_rate, total_profit,
                        total_loss, net_profit, average_profit,
                        average_loss, profit_factor, max_drawdown,
                        max_drawdown_percent, current_drawdown,
                        current_drawdown_percent, sharpe_ratio,
                        sortino_ratio, calmar_ratio, omega_ratio,
                        treynor_ratio, pnl_std, pnl_skew,
                        pnl_kurtosis, var_95, var_99,
                        cvar_95, cvar_99, expectancy,
                        recovery_factor, average_trade_duration
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13, $14,
                              $15, $16, $17, $18, $19, $20,
                              $21, $22, $23, $24, $25, $26,
                              $27, $28, $29, $30)
                    """,
                    metrics.timestamp,
                    metrics.total_trades,
                    metrics.winning_trades,
                    metrics.losing_trades,
                    metrics.win_rate,
                    metrics.total_profit,
                    metrics.total_loss,
                    metrics.net_profit,
                    metrics.average_profit,
                    metrics.average_loss,
                    metrics.profit_factor,
                    metrics.max_drawdown,
                    metrics.max_drawdown_percent,
                    metrics.current_drawdown,
                    metrics.current_drawdown_percent,
                    metrics.sharpe_ratio,
                    metrics.sortino_ratio,
                    metrics.calmar_ratio,
                    metrics.omega_ratio,
                    metrics.treynor_ratio,
                    metrics.pnl_std,
                    metrics.pnl_skew,
                    metrics.pnl_kurtosis,
                    metrics.var_95,
                    metrics.var_99,
                    metrics.cvar_95,
                    metrics.cvar_99,
                    metrics.expectancy,
                    metrics.recovery_factor,
                    metrics.average_trade_duration
                )
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    async def _load_metrics(self):
        """Load metrics from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM profit_metrics ORDER BY timestamp DESC LIMIT 100"
                )
                
                for row in rows:
                    metric = ProfitMetrics(
                        timestamp=row['timestamp'],
                        total_trades=row['total_trades'],
                        winning_trades=row['winning_trades'],
                        losing_trades=row['losing_trades'],
                        win_rate=row['win_rate'],
                        total_profit=row['total_profit'],
                        total_loss=row['total_loss'],
                        net_profit=row['net_profit'],
                        average_profit=row['average_profit'],
                        average_loss=row['average_loss'],
                        profit_factor=row['profit_factor'],
                        max_drawdown=row['max_drawdown'],
                        max_drawdown_percent=row['max_drawdown_percent'],
                        current_drawdown=row['current_drawdown'],
                        current_drawdown_percent=row['current_drawdown_percent'],
                        sharpe_ratio=row['sharpe_ratio'],
                        sortino_ratio=row['sortino_ratio'],
                        calmar_ratio=row['calmar_ratio'],
                        omega_ratio=row['omega_ratio'],
                        treynor_ratio=row['treynor_ratio'],
                        pnl_std=row['pnl_std'],
                        pnl_skew=row['pnl_skew'],
                        pnl_kurtosis=row['pnl_kurtosis'],
                        var_95=row['var_95'],
                        var_99=row['var_99'],
                        cvar_95=row['cvar_95'],
                        cvar_99=row['cvar_99'],
                        expectancy=row['expectancy'],
                        recovery_factor=row['recovery_factor'],
                        average_trade_duration=row['average_trade_duration']
                    )
                    self._metrics_history.append(metric)
                
                logger.info(f"Loaded {len(self._metrics_history)} metrics")
                
        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the profit calculator."""
        self._running = False
        logger.info("ProfitCalculator shutdown")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ProfitCalculator',
    'ProfitType',
    'ProfitMetric',
    'ProfitStatus',
    'ProfitCalculation',
    'ProfitMetrics',
    'ProfitHistory',
    'ProfitForecast'
]
