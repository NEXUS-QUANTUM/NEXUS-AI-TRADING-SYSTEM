# trading/bots/arbitrage_bot/core/arbitrage_types.py
# Nexus AI Trading System - Arbitrage Bot Types Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Types Module

This module provides comprehensive type definitions for the arbitrage bot
system, including:

- Arbitrage opportunity detection and classification
- Arbitrage execution models
- Risk management models
- Performance metrics
- Exchange and market data models
- Order and position models
- Configuration models
- Statistical models

The arbitrage bot supports:
- Cross-exchange arbitrage (CEX-CEX, CEX-DEX)
- Triangular arbitrage
- Statistical arbitrage
- Flash loan arbitrage
- Futures-spot arbitrage
- Cross-chain arbitrage
- Decentralized exchange (DEX) arbitrage
- Mixed arbitrage strategies
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Set
from pydantic import BaseModel, Field, validator, root_validator

# =============================================================================
# ARBITRAGE TYPES
# =============================================================================

class ArbitrageType(str, Enum):
    """Types of arbitrage strategies."""
    CROSS_EXCHANGE = "cross_exchange"
    TRIANGULAR = "triangular"
    STATISTICAL = "statistical"
    FLASH_LOAN = "flash_loan"
    FUTURES_SPOT = "futures_spot"
    CROSS_CHAIN = "cross_chain"
    DEX = "dex"
    MIXED = "mixed"
    CROSS_ASSET = "cross_asset"
    CROSS_MARKET = "cross_market"


class ArbitrageStatus(str, Enum):
    """Status of an arbitrage opportunity."""
    PENDING = "pending"
    DETECTED = "detected"
    VALIDATED = "validated"
    EXECUTING = "executing"
    EXECUTED = "executed"
    COMPLETED = "completed"
    PARTIALLY_EXECUTED = "partially_executed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class ArbitrageExecutionType(str, Enum):
    """Types of arbitrage execution."""
    ATOMIC = "atomic"  # Single transaction
    SEQUENTIAL = "sequential"  # Sequential execution
    PARALLEL = "parallel"  # Parallel execution
    BATCH = "batch"  # Batch execution
    SMART = "smart"  # Smart routing execution


class ArbitrageRiskLevel(str, Enum):
    """Risk levels for arbitrage."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ExchangeType(str, Enum):
    """Types of exchanges."""
    CEX = "cex"  # Centralized Exchange
    DEX = "dex"  # Decentralized Exchange
    MIXED = "mixed"  # Both CEX and DEX


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ArbitrageOpportunity(BaseModel):
    """
    Arbitrage opportunity model.
    
    Represents a detected arbitrage opportunity with all necessary
    information for execution decision and risk assessment.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ArbitrageType
    status: ArbitrageStatus = ArbitrageStatus.PENDING
    strategy_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Opportunity details
    symbol: str
    pair: str  # Standard pair format
    base_asset: str
    quote_asset: str
    
    # Price and spread
    buy_price: Decimal
    sell_price: Decimal
    spread: Decimal
    spread_percent: Decimal
    price_imbalance: Optional[Decimal] = None
    price_volatility: Optional[Decimal] = None
    
    # Volume and liquidity
    buy_volume: Decimal
    sell_volume: Decimal
    min_volume: Decimal
    max_volume: Decimal
    liquidity_score: Optional[Decimal] = None
    
    # Profit calculation
    gross_profit: Decimal
    net_profit: Decimal
    profit_percent: Decimal
    fee_total: Decimal
    gas_cost: Optional[Decimal] = None
    slippage_estimate: Optional[Decimal] = None
    
    # Risk assessment
    risk_level: ArbitrageRiskLevel = ArbitrageRiskLevel.MEDIUM
    risk_score: Decimal = Decimal('0')
    execution_risk: Decimal = Decimal('0')
    market_risk: Decimal = Decimal('0')
    counterparty_risk: Decimal = Decimal('0')
    operational_risk: Decimal = Decimal('0')
    
    # Execution information
    execution_type: ArbitrageExecutionType = ArbitrageExecutionType.SMART
    exchange_route: List[Dict[str, Any]] = Field(default_factory=list)
    required_capital: Decimal
    available_capital: Optional[Decimal] = None
    expected_duration: Optional[float] = None
    
    # Statistical information
    confidence_score: Decimal = Decimal('0')
    historical_win_rate: Optional[Decimal] = None
    expected_value: Optional[Decimal] = None
    max_loss: Optional[Decimal] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @property
    def is_profitable(self) -> bool:
        """Check if the opportunity is profitable."""
        return self.net_profit > 0

    @property
    def profit_factor(self) -> Decimal:
        """Calculate profit factor."""
        if self.fee_total == 0:
            return Decimal('inf')
        return self.gross_profit / self.fee_total

    @property
    def time_to_expiry(self) -> float:
        """Get time to expiry in seconds."""
        if not self.expires_at:
            return 0.0
        delta = self.expires_at - datetime.utcnow()
        return max(0.0, delta.total_seconds())


class ArbitrageExecution(BaseModel):
    """
    Arbitrage execution model.
    
    Represents the execution of an arbitrage opportunity with all
    transaction details and execution results.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_id: str
    type: ArbitrageType
    execution_type: ArbitrageExecutionType
    status: ArbitrageStatus = ArbitrageStatus.PENDING
    
    # Execution details
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    
    # Orders
    buy_order_id: Optional[str] = None
    sell_order_id: Optional[str] = None
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    buy_volume: Decimal
    sell_volume: Decimal
    
    # Results
    expected_profit: Decimal
    actual_profit: Decimal = Decimal('0')
    expected_profit_percent: Decimal
    actual_profit_percent: Decimal = Decimal('0')
    slippage: Decimal = Decimal('0')
    slippage_percent: Decimal = Decimal('0')
    
    # Fees and costs
    total_fees: Decimal = Decimal('0')
    buy_fee: Decimal = Decimal('0')
    sell_fee: Decimal = Decimal('0')
    gas_cost: Decimal = Decimal('0')
    execution_cost: Decimal = Decimal('0')
    
    # Risk metrics
    execution_risk_score: Decimal = Decimal('0')
    market_impact: Decimal = Decimal('0')
    
    # Performance
    fill_rate: Decimal = Decimal('0')
    execution_quality: Decimal = Decimal('0')
    latency: Optional[float] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None

    @property
    def is_successful(self) -> bool:
        """Check if the execution was successful."""
        return self.status == ArbitrageStatus.COMPLETED and self.actual_profit > 0

    @property
    def profit_difference(self) -> Decimal:
        """Calculate difference between expected and actual profit."""
        return self.actual_profit - self.expected_profit


class ExchangeConfig(BaseModel):
    """
    Exchange configuration model.
    
    Represents the configuration for an exchange used in arbitrage.
    """
    id: str
    name: str
    type: ExchangeType
    enabled: bool = True
    
    # Connection configuration
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    api_passphrase: Optional[str] = None
    base_url: Optional[str] = None
    ws_url: Optional[str] = None
    
    # Rate limits
    rate_limit_public: int = 20
    rate_limit_private: int = 10
    rate_limit_trade: int = 5
    
    # Fees
    maker_fee: Decimal = Decimal('0.001')  # 0.1%
    taker_fee: Decimal = Decimal('0.001')  # 0.1%
    withdrawal_fee: Optional[Decimal] = None
    deposit_fee: Optional[Decimal] = None
    
    # Trading limits
    min_trade_amount: Optional[Decimal] = None
    max_trade_amount: Optional[Decimal] = None
    min_notional: Optional[Decimal] = None
    max_notional: Optional[Decimal] = None
    
    # Features
    supports_websocket: bool = True
    supports_futures: bool = False
    supports_margin: bool = False
    supports_options: bool = False
    supports_staking: bool = False
    
    # Risk settings
    max_position_size: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None
    max_exposure: Optional[Decimal] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('maker_fee', 'taker_fee')
    def validate_fees(cls, v):
        if v < 0:
            raise ValueError("Fee cannot be negative")
        return v

    @validator('rate_limit_public', 'rate_limit_private', 'rate_limit_trade')
    def validate_rate_limits(cls, v):
        if v <= 0:
            raise ValueError("Rate limit must be positive")
        return v


class ArbitrageStrategyConfig(BaseModel):
    """
    Arbitrage strategy configuration model.
    
    Represents the configuration for an arbitrage strategy.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: ArbitrageType
    enabled: bool = True
    
    # Strategy parameters
    min_profit_percent: Decimal = Decimal('0.01')  # 0.01%
    min_profit_absolute: Decimal = Decimal('0.01')  # $0.01
    max_loss_percent: Decimal = Decimal('0.01')  # 1%
    max_slippage_percent: Decimal = Decimal('0.01')  # 1%
    min_confidence_score: Decimal = Decimal('0.6')  # 60%
    
    # Risk parameters
    max_position_size: Decimal = Decimal('1000')  # $1000
    max_drawdown: Decimal = Decimal('0.05')  # 5%
    max_exposure: Decimal = Decimal('10000')  # $10000
    max_risk_per_trade: Decimal = Decimal('0.02')  # 2%
    
    # Timing parameters
    opportunity_timeout: int = 30  # seconds
    execution_timeout: int = 60  # seconds
    min_time_between_trades: int = 5  # seconds
    max_execution_time: int = 10  # seconds
    
    # Exchange parameters
    exchanges: List[str] = Field(default_factory=list)
    symbols: List[str] = Field(default_factory=list)
    min_liquidity: Decimal = Decimal('1000')  # $1000
    max_spread: Decimal = Decimal('0.01')  # 1%
    
    # Execution parameters
    execution_type: ArbitrageExecutionType = ArbitrageExecutionType.SMART
    use_atomic_execution: bool = False
    use_parallel_execution: bool = True
    max_parallel_trades: int = 5
    
    # Analytics parameters
    track_performance: bool = True
    log_execution: bool = True
    send_alerts: bool = True
    alert_threshold: Decimal = Decimal('0.01')  # 1%
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('min_profit_percent', 'max_loss_percent', 'max_slippage_percent')
    def validate_percentages(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Percentage must be between 0 and 1")
        return v

    @validator('max_position_size', 'max_exposure', 'min_liquidity')
    def validate_amounts(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class ArbitrageStatisticalData(BaseModel):
    """
    Arbitrage statistical data model.
    
    Represents statistical data for arbitrage opportunities.
    """
    opportunity_id: str
    type: ArbitrageType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Price statistics
    mean_price: Decimal
    std_price: Decimal
    min_price: Decimal
    max_price: Decimal
    price_volatility: Decimal
    price_momentum: Optional[Decimal] = None
    
    # Spread statistics
    mean_spread: Decimal
    std_spread: Decimal
    min_spread: Decimal
    max_spread: Decimal
    spread_volatility: Decimal
    spread_imbalance: Optional[Decimal] = None
    
    # Volume statistics
    mean_volume: Decimal
    std_volume: Decimal
    min_volume: Decimal
    max_volume: Decimal
    volume_volatility: Decimal
    
    # Correlation statistics
    correlation_with_market: Optional[Decimal] = None
    correlation_with_asset: Optional[Decimal] = None
    
    # Z-scores
    price_z_score: Decimal
    spread_z_score: Decimal
    volume_z_score: Decimal
    
    # Confidence metrics
    confidence_score: Decimal
    entropy: Optional[Decimal] = None
    kurtosis: Optional[Decimal] = None
    skewness: Optional[Decimal] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArbitrageRiskMetrics(BaseModel):
    """
    Arbitrage risk metrics model.
    
    Represents comprehensive risk metrics for arbitrage operations.
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # VaR metrics
    var_95: Decimal  # Value at Risk at 95%
    var_99: Decimal  # Value at Risk at 99%
    cvar_95: Decimal  # Conditional VaR at 95%
    cvar_99: Decimal  # Conditional VaR at 99%
    
    # Drawdown metrics
    max_drawdown: Decimal
    max_drawdown_percent: Decimal
    average_drawdown: Decimal
    average_drawdown_percent: Decimal
    
    # Sharpe and related
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    omega_ratio: Decimal
    
    # Beta and correlation
    beta: Decimal
    correlation_with_market: Decimal
    correlation_with_asset: Decimal
    
    # Risk contribution
    market_risk_contribution: Decimal
    liquidity_risk_contribution: Decimal
    operational_risk_contribution: Decimal
    counterparty_risk_contribution: Decimal
    
    # Stress test metrics
    stress_test_loss_95: Decimal
    stress_test_loss_99: Decimal
    worst_case_loss: Decimal
    
    # Risk score
    overall_risk_score: Decimal
    risk_rating: ArbitrageRiskLevel
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArbitragePerformanceMetrics(BaseModel):
    """
    Arbitrage performance metrics model.
    
    Represents performance metrics for arbitrage strategies.
    """
    strategy_id: str
    timeframe: str  # daily, weekly, monthly, yearly
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Core metrics
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    win_rate: Decimal = Decimal('0')
    
    # Profit metrics
    total_profit: Decimal = Decimal('0')
    total_loss: Decimal = Decimal('0')
    net_profit: Decimal = Decimal('0')
    average_profit: Decimal = Decimal('0')
    average_loss: Decimal = Decimal('0')
    profit_factor: Decimal = Decimal('0')
    
    # Trade metrics
    average_trade_duration: float = 0.0
    max_trade_duration: float = 0.0
    min_trade_duration: float = 0.0
    trades_per_hour: float = 0.0
    
    # Return metrics
    return_percent: Decimal = Decimal('0')
    annualized_return: Decimal = Decimal('0')
    cumulative_return: Decimal = Decimal('0')
    
    # Risk metrics
    max_drawdown: Decimal = Decimal('0')
    max_drawdown_percent: Decimal = Decimal('0')
    sharpe_ratio: Decimal = Decimal('0')
    sortino_ratio: Decimal = Decimal('0')
    calmar_ratio: Decimal = Decimal('0')
    
    # Volume metrics
    total_volume: Decimal = Decimal('0')
    average_volume: Decimal = Decimal('0')
    max_volume: Decimal = Decimal('0')
    min_volume: Decimal = Decimal('0')
    
    # Fee metrics
    total_fees: Decimal = Decimal('0')
    average_fee: Decimal = Decimal('0')
    fee_percentage: Decimal = Decimal('0')
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def profit_ratio(self) -> Decimal:
        """Calculate profit ratio (net profit / total volume)."""
        if self.total_volume == 0:
            return Decimal('0')
        return self.net_profit / self.total_volume


# =============================================================================
# STATISTICAL MODELS
# =============================================================================

@dataclass
class StatisticalArbitrageModel:
    """
    Statistical arbitrage model.
    
    Represents a statistical arbitrage model based on mean reversion,
    cointegration, or other statistical relationships.
    """
    symbol: str
    model_type: str  # mean_reversion, cointegration, machine_learning
    training_start: datetime
    training_end: datetime
    lookback_period: int = 100
    confidence_threshold: float = 2.0
    
    # Model parameters
    mean: float = 0.0
    std: float = 0.0
    half_life: Optional[float] = None
    cointegration_coefficient: Optional[float] = None
    spread_mean: Optional[float] = None
    spread_std: Optional[float] = None
    
    # Machine learning parameters
    model_file: Optional[str] = None
    feature_importance: Optional[Dict[str, float]] = None
    accuracy: Optional[float] = None
    
    # Performance
    sharpe_ratio: Optional[float] = None
    hit_ratio: Optional[float] = None
    maximum_drawdown: Optional[float] = None
    
    # Status
    is_trained: bool = False
    last_trained: Optional[datetime] = None
    active: bool = False

    def get_z_score(self, current_spread: float) -> float:
        """Calculate z-score of current spread."""
        if self.std == 0:
            return 0.0
        return (current_spread - self.mean) / self.std

    def is_signal(self, current_spread: float) -> Tuple[bool, str]:
        """Determine if there's a trading signal."""
        z_score = self.get_z_score(current_spread)
        
        if z_score > self.confidence_threshold:
            return True, "short"  # Sell signal (overpriced)
        elif z_score < -self.confidence_threshold:
            return True, "long"  # Buy signal (underpriced)
        return False, "neutral"

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'symbol': self.symbol,
            'model_type': self.model_type,
            'training_start': self.training_start.isoformat(),
            'training_end': self.training_end.isoformat(),
            'lookback_period': self.lookback_period,
            'confidence_threshold': self.confidence_threshold,
            'mean': self.mean,
            'std': self.std,
            'half_life': self.half_life,
            'cointegration_coefficient': self.cointegration_coefficient,
            'spread_mean': self.spread_mean,
            'spread_std': self.spread_std,
            'is_trained': self.is_trained,
            'last_trained': self.last_trained.isoformat() if self.last_trained else None,
            'active': self.active
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_arbitrage_profit(
    buy_price: Decimal,
    sell_price: Decimal,
    volume: Decimal,
    buy_fee: Decimal,
    sell_fee: Decimal,
    gas_cost: Optional[Decimal] = None
) -> Dict[str, Decimal]:
    """
    Calculate arbitrage profit and related metrics.
    
    Args:
        buy_price: Price at buy exchange
        sell_price: Price at sell exchange
        volume: Trade volume
        buy_fee: Fee at buy exchange (rate)
        sell_fee: Fee at sell exchange (rate)
        gas_cost: Gas cost for transaction
        
    Returns:
        Dict with profit metrics
    """
    buy_cost = buy_price * volume
    sell_revenue = sell_price * volume
    
    buy_fee_amount = buy_cost * buy_fee
    sell_fee_amount = sell_revenue * sell_fee
    
    gross_profit = sell_revenue - buy_cost
    net_profit = gross_profit - buy_fee_amount - sell_fee_amount
    
    if gas_cost:
        net_profit -= gas_cost
    
    profit_percent = (net_profit / buy_cost) * 100
    
    return {
        'buy_cost': buy_cost,
        'sell_revenue': sell_revenue,
        'gross_profit': gross_profit,
        'net_profit': net_profit,
        'profit_percent': profit_percent,
        'buy_fee_amount': buy_fee_amount,
        'sell_fee_amount': sell_fee_amount,
        'total_fees': buy_fee_amount + sell_fee_amount + (gas_cost or Decimal('0'))
    }


def calculate_risk_score(
    volatility: Decimal,
    liquidity: Decimal,
    spread: Decimal,
    execution_time: float,
    confidence: Decimal
) -> Decimal:
    """
    Calculate a risk score for an arbitrage opportunity.
    
    Args:
        volatility: Price volatility
        liquidity: Market liquidity
        spread: Price spread
        execution_time: Expected execution time
        confidence: Confidence score
        
    Returns:
        Risk score (0-100)
    """
    # Normalize components
    vol_score = min(volatility * 10, 100)  # 0-100
    liq_score = max(0, 100 - (liquidity * 10))  # 0-100 (higher liquidity = lower score)
    spread_score = min(spread * 100, 100)  # 0-100
    time_score = min(execution_time * 2, 100)  # 0-100
    conf_score = 100 - (confidence * 100)  # 0-100
    
    # Weighted average
    weights = {
        'volatility': 0.25,
        'liquidity': 0.20,
        'spread': 0.20,
        'execution_time': 0.15,
        'confidence': 0.20
    }
    
    risk = (
        vol_score * weights['volatility'] +
        liq_score * weights['liquidity'] +
        spread_score * weights['spread'] +
        time_score * weights['execution_time'] +
        conf_score * weights['confidence']
    )
    
    return risk.quantize(Decimal('0.01'))


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    'ArbitrageType',
    'ArbitrageStatus',
    'ArbitrageExecutionType',
    'ArbitrageRiskLevel',
    'ExchangeType',
    'OrderStatus',
    
    # Models
    'ArbitrageOpportunity',
    'ArbitrageExecution',
    'ExchangeConfig',
    'ArbitrageStrategyConfig',
    'ArbitrageStatisticalData',
    'ArbitrageRiskMetrics',
    'ArbitragePerformanceMetrics',
    'StatisticalArbitrageModel',
    
    # Helper functions
    'calculate_arbitrage_profit',
    'calculate_risk_score',
]
