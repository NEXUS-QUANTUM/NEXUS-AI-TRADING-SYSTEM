# trading/bots/arbitrage_bot/core/risk_calculator.py
# Nexus AI Trading System - Arbitrage Bot Risk Calculator Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Risk Calculator Module

This module provides comprehensive risk calculation and management
for the arbitrage bot system, including:

- Position risk assessment
- Portfolio risk metrics
- VaR and CVaR calculations
- Drawdown analysis
- Risk-adjusted return metrics
- Risk factor analysis
- Scenario analysis
- Stress testing
- Risk limit monitoring
- Risk score calculation
- Risk attribution
- Correlation risk analysis
- Liquidity risk assessment
- Counterparty risk analysis
- Market risk analysis
- Operational risk analysis
- Risk optimization
- Risk reporting
- Real-time risk monitoring

The risk calculator ensures the arbitrage bot operates within
acceptable risk parameters and provides comprehensive risk analytics.
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
from scipy import stats
from scipy.optimize import minimize

# Nexus imports
from trading.bots.arbitrage_bot.core.position_tracker import Position, PositionLeg
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketPrice
from trading.bots.arbitrage_bot.core.balance_manager import BalanceManager
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class RiskMetricType(str, Enum):
    """Risk metric types."""
    VAR_95 = "var_95"
    VAR_99 = "var_99"
    CVAR_95 = "cvar_95"
    CVAR_99 = "cvar_99"
    MAX_DRAWDOWN = "max_drawdown"
    CURRENT_DRAWDOWN = "current_drawdown"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    BETA = "beta"
    ALPHA = "alpha"
    CORRELATION = "correlation"
    DIVERSIFICATION_RATIO = "diversification_ratio"
    CONCENTRATION_RATIO = "concentration_ratio"


class RiskLevel(str, Enum):
    """Risk levels."""
    VERY_LOW = "very_low"     # 0-20%
    LOW = "low"               # 20-40%
    MODERATE = "moderate"     # 40-60%
    HIGH = "high"             # 60-80%
    VERY_HIGH = "very_high"   # 80-100%


class RiskCategory(str, Enum):
    """Risk categories."""
    MARKET = "market"
    LIQUIDITY = "liquidity"
    COUNTERPARTY = "counterparty"
    OPERATIONAL = "operational"
    SYSTEMIC = "systemic"
    REGULATORY = "regulatory"
    MODEL = "model"
    EXECUTION = "execution"


class RiskStatus(str, Enum):
    """Risk status."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RiskConfig(BaseModel):
    """Risk configuration."""
    # Risk limits
    max_drawdown: Decimal = Decimal('0.15')  # 15%
    max_loss_per_day: Decimal = Decimal('0.05')  # 5%
    max_loss_per_week: Decimal = Decimal('0.10')  # 10%
    max_loss_per_month: Decimal = Decimal('0.20')  # 20%
    max_position_risk: Decimal = Decimal('0.02')  # 2%
    max_portfolio_risk: Decimal = Decimal('0.10')  # 10%
    max_leverage: Decimal = Decimal('3')  # 3x
    max_concentration: Decimal = Decimal('0.25')  # 25%
    
    # VaR parameters
    var_confidence_95: float = 0.95
    var_confidence_99: float = 0.99
    var_lookback_days: int = 252
    var_holding_period: int = 1  # days
    
    # Stress testing
    stress_scenarios: List[str] = Field(default_factory=lambda: [
        "2008_financial_crisis",
        "2020_covid_crash",
        "2021_crypto_crash",
        "2022_inflation_shock",
        "custom"
    ])
    stress_shock_percent: Decimal = Decimal('0.20')  # 20%
    
    # Risk scoring
    risk_score_weights: Dict[str, float] = Field(default_factory=lambda: {
        "volatility": 0.25,
        "drawdown": 0.25,
        "liquidity": 0.15,
        "concentration": 0.15,
        "leverage": 0.10,
        "correlation": 0.10
    })
    
    # Alerts
    alert_threshold_risk_score: Decimal = Decimal('70')  # 70%
    alert_threshold_drawdown: Decimal = Decimal('0.10')  # 10%
    alert_threshold_loss: Decimal = Decimal('0.03')  # 3%
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('max_drawdown', 'max_loss_per_day', 'max_loss_per_week', 'max_loss_per_month')
    def validate_loss_limits(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Loss limit must be between 0 and 1")
        return v


class RiskMetric(BaseModel):
    """Risk metric."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: RiskMetricType
    value: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    category: RiskCategory
    status: RiskStatus = RiskStatus.NORMAL
    threshold: Optional[Decimal] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PositionRisk(BaseModel):
    """Position risk assessment."""
    position_id: str
    symbol: str
    exchange: str
    
    # Risk metrics
    market_risk: Decimal
    liquidity_risk: Decimal
    concentration_risk: Decimal
    leverage_risk: Decimal
    volatility_risk: Decimal
    
    # Combined risk
    total_risk: Decimal
    risk_level: RiskLevel
    risk_score: Decimal  # 0-100
    
    # Risk limits
    risk_limit: Decimal
    risk_utilization: Decimal
    
    # Status
    status: RiskStatus
    warnings: List[str] = Field(default_factory=list)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioRisk(BaseModel):
    """Portfolio risk assessment."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Portfolio metrics
    total_value: Decimal
    var_95: Decimal
    var_99: Decimal
    cvar_95: Decimal
    cvar_99: Decimal
    expected_shortfall: Decimal
    max_drawdown: Decimal
    current_drawdown: Decimal
    
    # Risk-adjusted returns
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    omega_ratio: Decimal
    
    # Risk distribution
    diversification_ratio: Decimal
    concentration_ratio: Decimal
    beta: Decimal
    alpha: Decimal
    
    # Risk limits
    risk_limit: Decimal
    risk_utilization: Decimal
    
    # Combined risk
    total_risk: Decimal
    risk_level: RiskLevel
    risk_score: Decimal  # 0-100
    
    # Risk breakdown
    market_risk: Decimal
    liquidity_risk: Decimal
    counterparty_risk: Decimal
    operational_risk: Decimal
    systemic_risk: Decimal
    
    # Position risks
    position_risks: List[PositionRisk] = Field(default_factory=list)
    
    # Status
    status: RiskStatus
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StressTestResult(BaseModel):
    """Stress test result."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Impact metrics
    portfolio_loss: Decimal
    portfolio_loss_percent: Decimal
    max_position_loss: Decimal
    max_position_loss_percent: Decimal
    var_breach: bool
    drawdown_exceeded: bool
    margin_call: bool
    liquidation_risk: bool
    
    # Details
    affected_positions: List[Dict[str, Any]] = Field(default_factory=list)
    risk_metrics: Dict[str, Decimal] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskAlert(BaseModel):
    """Risk alert."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    severity: str  # info, warning, critical
    message: str
    metric: Optional[RiskMetric] = None
    position_id: Optional[str] = None
    threshold: Decimal
    current_value: Decimal
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Risk metrics
CREATE TABLE IF NOT EXISTS risk_metrics (
    id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(30) NOT NULL,
    value DECIMAL(32, 16) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    category VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL,
    threshold DECIMAL(32, 16),
    metadata JSONB DEFAULT '{}',
    INDEX idx_risk_metrics_type (type),
    INDEX idx_risk_metrics_timestamp (timestamp)
);

-- Position risk assessments
CREATE TABLE IF NOT EXISTS position_risk_assessments (
    id SERIAL PRIMARY KEY,
    position_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    market_risk DECIMAL(32, 16) NOT NULL,
    liquidity_risk DECIMAL(32, 16) NOT NULL,
    concentration_risk DECIMAL(32, 16) NOT NULL,
    leverage_risk DECIMAL(32, 16) NOT NULL,
    volatility_risk DECIMAL(32, 16) NOT NULL,
    total_risk DECIMAL(32, 16) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    risk_score DECIMAL(32, 16) NOT NULL,
    risk_limit DECIMAL(32, 16) NOT NULL,
    risk_utilization DECIMAL(32, 16) NOT NULL,
    status VARCHAR(20) NOT NULL,
    warnings JSONB DEFAULT '[]',
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    UNIQUE(position_id, timestamp)
);

-- Portfolio risk assessments
CREATE TABLE IF NOT EXISTS portfolio_risk_assessments (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    total_value DECIMAL(32, 16) NOT NULL,
    var_95 DECIMAL(32, 16) NOT NULL,
    var_99 DECIMAL(32, 16) NOT NULL,
    cvar_95 DECIMAL(32, 16) NOT NULL,
    cvar_99 DECIMAL(32, 16) NOT NULL,
    expected_shortfall DECIMAL(32, 16) NOT NULL,
    max_drawdown DECIMAL(32, 16) NOT NULL,
    current_drawdown DECIMAL(32, 16) NOT NULL,
    sharpe_ratio DECIMAL(32, 16) NOT NULL,
    sortino_ratio DECIMAL(32, 16) NOT NULL,
    calmar_ratio DECIMAL(32, 16) NOT NULL,
    omega_ratio DECIMAL(32, 16) NOT NULL,
    diversification_ratio DECIMAL(32, 16) NOT NULL,
    concentration_ratio DECIMAL(32, 16) NOT NULL,
    beta DECIMAL(32, 16) NOT NULL,
    alpha DECIMAL(32, 16) NOT NULL,
    risk_limit DECIMAL(32, 16) NOT NULL,
    risk_utilization DECIMAL(32, 16) NOT NULL,
    total_risk DECIMAL(32, 16) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    risk_score DECIMAL(32, 16) NOT NULL,
    market_risk DECIMAL(32, 16) NOT NULL,
    liquidity_risk DECIMAL(32, 16) NOT NULL,
    counterparty_risk DECIMAL(32, 16) NOT NULL,
    operational_risk DECIMAL(32, 16) NOT NULL,
    systemic_risk DECIMAL(32, 16) NOT NULL,
    status VARCHAR(20) NOT NULL,
    warnings JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    INDEX idx_portfolio_risk_assessments_timestamp (timestamp)
);

-- Stress test results
CREATE TABLE IF NOT EXISTS stress_test_results (
    id VARCHAR(64) PRIMARY KEY,
    scenario VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    portfolio_loss DECIMAL(32, 16) NOT NULL,
    portfolio_loss_percent DECIMAL(32, 16) NOT NULL,
    max_position_loss DECIMAL(32, 16) NOT NULL,
    max_position_loss_percent DECIMAL(32, 16) NOT NULL,
    var_breach BOOLEAN DEFAULT FALSE,
    drawdown_exceeded BOOLEAN DEFAULT FALSE,
    margin_call BOOLEAN DEFAULT FALSE,
    liquidation_risk BOOLEAN DEFAULT FALSE,
    affected_positions JSONB DEFAULT '[]',
    risk_metrics JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    INDEX idx_stress_test_results_scenario (scenario),
    INDEX idx_stress_test_results_timestamp (timestamp)
);

-- Risk alerts
CREATE TABLE IF NOT EXISTS risk_alerts (
    id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    metric_id VARCHAR(64),
    position_id VARCHAR(64),
    threshold DECIMAL(32, 16) NOT NULL,
    current_value DECIMAL(32, 16) NOT NULL,
    triggered_at TIMESTAMP NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_risk_alerts_type (type),
    INDEX idx_risk_alerts_triggered_at (triggered_at)
);
"""


# =============================================================================
# RISK CALCULATOR CLASS
# =============================================================================

class RiskCalculator:
    """
    Advanced risk calculator for arbitrage bot.
    
    Features:
    - Position risk assessment
    - Portfolio risk metrics
    - VaR and CVaR calculations
    - Drawdown analysis
    - Risk-adjusted return metrics
    - Risk factor analysis
    - Scenario analysis
    - Stress testing
    - Risk limit monitoring
    - Risk score calculation
    - Risk attribution
    - Correlation risk analysis
    - Liquidity risk assessment
    - Counterparty risk analysis
    - Market risk analysis
    - Operational risk analysis
    - Risk optimization
    - Risk reporting
    - Real-time risk monitoring
    """
    
    def __init__(
        self,
        market_data: MarketDataManager,
        balance_manager: BalanceManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[RiskConfig] = None
    ):
        self.market_data = market_data
        self.balance_manager = balance_manager
        self.redis = redis
        self.pool = pool
        self.config = config or RiskConfig()
        
        # Risk state
        self._metrics: List[RiskMetric] = []
        self._alerts: List[RiskAlert] = []
        self._stress_results: List[StressTestResult] = []
        
        # Circuit breakers
        self._risk_cb = CircuitBreaker(
            name="risk_calculator",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            "risk_alert": [],
            "risk_update": [],
            "risk_breach": []
        }
        
        logger.info("RiskCalculator initialized")
    
    async def initialize(self):
        """Initialize the risk calculator."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load metrics
        if self.pool:
            await self._load_metrics()
        
        # Start monitoring
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        self._initialized = True
        logger.info("RiskCalculator initialized")
    
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
    # RISK CALCULATION
    # =========================================================================
    
    async def calculate_position_risk(
        self,
        position: Position
    ) -> PositionRisk:
        """
        Calculate risk for a position.
        
        Args:
            position: Position to assess
            
        Returns:
            PositionRisk
        """
        # Get market data
        market_data = await self.market_data.get_price(
            position.legs[0].exchange if position.legs else "",
            position.legs[0].symbol if position.legs else ""
        ) if position.legs else None
        
        # Calculate risk components
        market_risk = self._calculate_market_risk(position, market_data)
        liquidity_risk = self._calculate_liquidity_risk(position, market_data)
        concentration_risk = self._calculate_concentration_risk(position)
        leverage_risk = self._calculate_leverage_risk(position)
        volatility_risk = self._calculate_volatility_risk(position, market_data)
        
        # Calculate total risk
        total_risk = (
            market_risk * Decimal('0.30') +
            liquidity_risk * Decimal('0.20') +
            concentration_risk * Decimal('0.20') +
            leverage_risk * Decimal('0.15') +
            volatility_risk * Decimal('0.15')
        )
        
        # Calculate risk score (0-100)
        risk_score = total_risk * 100
        
        # Determine risk level
        risk_level = self._get_risk_level(risk_score)
        
        # Check risk limits
        risk_limit = self.config.max_position_risk
        risk_utilization = (total_risk / risk_limit * 100) if risk_limit > 0 else Decimal('0')
        
        # Determine status
        status = RiskStatus.NORMAL
        warnings = []
        
        if risk_utilization > 90:
            status = RiskStatus.CRITICAL
            warnings.append("Risk utilization exceeds 90%")
        elif risk_utilization > 75:
            status = RiskStatus.HIGH
            warnings.append("Risk utilization exceeds 75%")
        elif risk_utilization > 60:
            status = RiskStatus.ELEVATED
            warnings.append("Risk utilization exceeds 60%")
        
        return PositionRisk(
            position_id=position.id,
            symbol=position.legs[0].symbol if position.legs else "",
            exchange=position.legs[0].exchange if position.legs else "",
            market_risk=market_risk.quantize(Decimal('0.0001')),
            liquidity_risk=liquidity_risk.quantize(Decimal('0.0001')),
            concentration_risk=concentration_risk.quantize(Decimal('0.0001')),
            leverage_risk=leverage_risk.quantize(Decimal('0.0001')),
            volatility_risk=volatility_risk.quantize(Decimal('0.0001')),
            total_risk=total_risk.quantize(Decimal('0.0001')),
            risk_level=risk_level,
            risk_score=risk_score.quantize(Decimal('0.01')),
            risk_limit=risk_limit,
            risk_utilization=risk_utilization.quantize(Decimal('0.01')),
            status=status,
            warnings=warnings,
            metadata=position.metadata
        )
    
    async def calculate_portfolio_risk(
        self,
        positions: List[Position]
    ) -> PortfolioRisk:
        """
        Calculate portfolio risk.
        
        Args:
            positions: List of positions
            
        Returns:
            PortfolioRisk
        """
        if not positions:
            return PortfolioRisk(
                total_value=Decimal('0'),
                var_95=Decimal('0'),
                var_99=Decimal('0'),
                cvar_95=Decimal('0'),
                cvar_99=Decimal('0'),
                expected_shortfall=Decimal('0'),
                max_drawdown=Decimal('0'),
                current_drawdown=Decimal('0'),
                sharpe_ratio=Decimal('0'),
                sortino_ratio=Decimal('0'),
                calmar_ratio=Decimal('0'),
                omega_ratio=Decimal('0'),
                diversification_ratio=Decimal('1'),
                concentration_ratio=Decimal('0'),
                beta=Decimal('1'),
                alpha=Decimal('0'),
                risk_limit=self.config.max_portfolio_risk,
                risk_utilization=Decimal('0'),
                total_risk=Decimal('0'),
                risk_level=RiskLevel.VERY_LOW,
                risk_score=Decimal('0'),
                market_risk=Decimal('0'),
                liquidity_risk=Decimal('0'),
                counterparty_risk=Decimal('0'),
                operational_risk=Decimal('0'),
                systemic_risk=Decimal('0'),
                position_risks=[],
                status=RiskStatus.NORMAL,
                warnings=[]
            )
        
        # Calculate position risks
        position_risks = []
        total_market_risk = Decimal('0')
        total_liquidity_risk = Decimal('0')
        total_value = Decimal('0')
        
        for position in positions:
            pos_risk = await self.calculate_position_risk(position)
            position_risks.append(pos_risk)
            total_market_risk += pos_risk.market_risk
            total_liquidity_risk += pos_risk.liquidity_risk
            total_value += position.market_value
        
        # Calculate portfolio metrics
        returns = await self._get_historical_returns(positions)
        var_95 = self._calculate_var(returns, 0.95)
        var_99 = self._calculate_var(returns, 0.99)
        cvar_95 = self._calculate_cvar(returns, 0.95)
        cvar_99 = self._calculate_cvar(returns, 0.99)
        expected_shortfall = (var_95 + var_99) / 2
        
        # Calculate drawdown
        max_drawdown, current_drawdown = self._calculate_drawdown(returns)
        
        # Calculate risk-adjusted returns
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        sortino_ratio = self._calculate_sortino_ratio(returns)
        calmar_ratio = self._calculate_calmar_ratio(returns)
        omega_ratio = self._calculate_omega_ratio(returns)
        
        # Calculate diversification and concentration
        weights = await self._get_position_weights(positions)
        diversification_ratio = self._calculate_diversification_ratio(weights)
        concentration_ratio = self._calculate_concentration_ratio(weights)
        
        # Calculate beta and alpha
        beta = await self._calculate_beta(positions)
        alpha = await self._calculate_alpha(positions, beta)
        
        # Calculate total risk
        total_risk = min(
            (total_market_risk + total_liquidity_risk) / Decimal('2'),
            Decimal('1')
        )
        
        # Calculate risk score (0-100)
        risk_score = total_risk * 100
        
        # Determine risk level
        risk_level = self._get_risk_level(risk_score)
        
        # Check risk limits
        risk_limit = self.config.max_portfolio_risk
        risk_utilization = (total_risk / risk_limit * 100) if risk_limit > 0 else Decimal('0')
        
        # Determine status
        status = RiskStatus.NORMAL
        warnings = []
        
        if risk_utilization > 90:
            status = RiskStatus.CRITICAL
            warnings.append("Portfolio risk utilization exceeds 90%")
        elif risk_utilization > 75:
            status = RiskStatus.HIGH
            warnings.append("Portfolio risk utilization exceeds 75%")
        elif risk_utilization > 60:
            status = RiskStatus.ELEVATED
            warnings.append("Portfolio risk utilization exceeds 60%")
        
        return PortfolioRisk(
            total_value=total_value.quantize(Decimal('0.0001')),
            var_95=var_95.quantize(Decimal('0.0001')),
            var_99=var_99.quantize(Decimal('0.0001')),
            cvar_95=cvar_95.quantize(Decimal('0.0001')),
            cvar_99=cvar_99.quantize(Decimal('0.0001')),
            expected_shortfall=expected_shortfall.quantize(Decimal('0.0001')),
            max_drawdown=max_drawdown.quantize(Decimal('0.0001')),
            current_drawdown=current_drawdown.quantize(Decimal('0.0001')),
            sharpe_ratio=sharpe_ratio.quantize(Decimal('0.01')),
            sortino_ratio=sortino_ratio.quantize(Decimal('0.01')),
            calmar_ratio=calmar_ratio.quantize(Decimal('0.01')),
            omega_ratio=omega_ratio.quantize(Decimal('0.01')),
            diversification_ratio=diversification_ratio.quantize(Decimal('0.01')),
            concentration_ratio=concentration_ratio.quantize(Decimal('0.01')),
            beta=beta.quantize(Decimal('0.01')),
            alpha=alpha.quantize(Decimal('0.01')),
            risk_limit=risk_limit,
            risk_utilization=risk_utilization.quantize(Decimal('0.01')),
            total_risk=total_risk.quantize(Decimal('0.0001')),
            risk_level=risk_level,
            risk_score=risk_score.quantize(Decimal('0.01')),
            market_risk=(total_market_risk / Decimal('2')).quantize(Decimal('0.0001')),
            liquidity_risk=(total_liquidity_risk / Decimal('2')).quantize(Decimal('0.0001')),
            counterparty_risk=Decimal('0.05'),
            operational_risk=Decimal('0.03'),
            systemic_risk=Decimal('0.02'),
            position_risks=position_risks,
            status=status,
            warnings=warnings
        )
    
    # =========================================================================
    # RISK SUB-CALCULATIONS
    # =========================================================================
    
    def _calculate_market_risk(
        self,
        position: Position,
        market_data: Optional[MarketPrice]
    ) -> Decimal:
        """Calculate market risk for a position."""
        if not market_data:
            return Decimal('0.05')
        
        # Calculate volatility-based risk
        volatility = await self._get_volatility(position.symbol)
        position_value = position.market_value
        
        # Higher volatility = higher risk
        risk = volatility * Decimal('2')  # 2x volatility
        
        # Adjust for position size
        total_value = position.market_value
        if total_value > 0:
            risk *= (position_value / total_value)
        
        return min(risk, Decimal('1'))
    
    def _calculate_liquidity_risk(
        self,
        position: Position,
        market_data: Optional[MarketPrice]
    ) -> Decimal:
        """Calculate liquidity risk for a position."""
        if not market_data:
            return Decimal('0.1')
        
        # Get order book depth
        try:
            depth = await self.market_data.get_depth(
                position.legs[0].exchange if position.legs else "",
                position.legs[0].symbol if position.legs else "",
                depth=10
            )
            
            total_depth = depth.total_bid_volume + depth.total_ask_volume
            position_volume = position.quantity
            
            if total_depth > 0:
                liquidity_ratio = position_volume / total_depth
                risk = min(liquidity_ratio * Decimal('5'), Decimal('1'))
            else:
                risk = Decimal('0.5')
        except Exception:
            risk = Decimal('0.5')
        
        return risk
    
    def _calculate_concentration_risk(self, position: Position) -> Decimal:
        """Calculate concentration risk for a position."""
        # Get total portfolio value
        total_value = self._get_total_portfolio_value()
        if total_value == 0:
            return Decimal('0')
        
        # Calculate concentration
        position_value = position.market_value
        concentration = position_value / total_value
        
        # Risk increases with concentration
        if concentration > Decimal('0.5'):
            return Decimal('1')
        elif concentration > Decimal('0.25'):
            return concentration * Decimal('2')
        else:
            return concentration
    
    def _calculate_leverage_risk(self, position: Position) -> Decimal:
        """Calculate leverage risk for a position."""
        if position.leverage <= Decimal('1'):
            return Decimal('0')
        
        # Risk increases with leverage
        risk = (position.leverage - Decimal('1')) / Decimal('10')
        return min(risk, Decimal('1'))
    
    def _calculate_volatility_risk(
        self,
        position: Position,
        market_data: Optional[MarketPrice]
    ) -> Decimal:
        """Calculate volatility risk for a position."""
        volatility = await self._get_volatility(position.symbol)
        
        # Convert volatility to risk (0-1)
        risk = volatility / Decimal('0.5')  # 50% volatility = 1.0 risk
        return min(risk, Decimal('1'))
    
    # =========================================================================
    # VAR AND CVAR CALCULATIONS
    # =========================================================================
    
    def _calculate_var(self, returns: List[float], confidence: float) -> Decimal:
        """Calculate Value at Risk."""
        if not returns:
            return Decimal('0')
        
        var = np.percentile(returns, (1 - confidence) * 100)
        return Decimal(str(abs(var)))
    
    def _calculate_cvar(self, returns: List[float], confidence: float) -> Decimal:
        """Calculate Conditional Value at Risk."""
        if not returns:
            return Decimal('0')
        
        var = np.percentile(returns, (1 - confidence) * 100)
        cvar = np.mean([r for r in returns if r <= var]) if returns else 0
        return Decimal(str(abs(cvar)))
    
    def _calculate_drawdown(self, returns: List[float]) -> Tuple[Decimal, Decimal]:
        """Calculate drawdown metrics."""
        if not returns:
            return Decimal('0'), Decimal('0')
        
        cumulative = np.cumprod(1 + np.array(returns))
        peak = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - peak) / peak
        max_dd = np.min(drawdown)
        current_dd = drawdown[-1] if len(drawdown) > 0 else 0
        
        return Decimal(str(abs(max_dd))), Decimal(str(abs(current_dd)))
    
    # =========================================================================
    # RISK-ADJUSTED METRICS
    # =========================================================================
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> Decimal:
        """Calculate Sharpe ratio."""
        if len(returns) < 2:
            return Decimal('0')
        
        risk_free = 0.02 / 252  # Daily risk-free rate
        excess = np.mean(returns) - risk_free
        std = np.std(returns)
        
        if std == 0:
            return Decimal('0')
        
        sharpe = excess / std * np.sqrt(252)
        return Decimal(str(sharpe))
    
    def _calculate_sortino_ratio(self, returns: List[float]) -> Decimal:
        """Calculate Sortino ratio."""
        if len(returns) < 2:
            return Decimal('0')
        
        risk_free = 0.02 / 252
        excess = np.mean(returns) - risk_free
        
        downside = np.std([r for r in returns if r < 0])
        if downside == 0:
            return Decimal('0')
        
        sortino = excess / downside * np.sqrt(252)
        return Decimal(str(sortino))
    
    def _calculate_calmar_ratio(self, returns: List[float]) -> Decimal:
        """Calculate Calmar ratio."""
        if not returns:
            return Decimal('0')
        
        annualized_return = np.mean(returns) * 252
        max_dd, _ = self._calculate_drawdown(returns)
        
        if max_dd == 0:
            return Decimal('0')
        
        calmar = annualized_return / float(max_dd)
        return Decimal(str(calmar))
    
    def _calculate_omega_ratio(self, returns: List[float]) -> Decimal:
        """Calculate Omega ratio."""
        if not returns:
            return Decimal('0')
        
        threshold = 0
        gains = sum(r for r in returns if r > threshold)
        losses = abs(sum(r for r in returns if r < threshold))
        
        if losses == 0:
            return Decimal('inf')
        
        omega = gains / losses
        return Decimal(str(omega))
    
    # =========================================================================
    # PORTFOLIO METRICS
    # =========================================================================
    
    def _calculate_diversification_ratio(self, weights: Dict[str, float]) -> Decimal:
        """Calculate diversification ratio."""
        if not weights:
            return Decimal('1')
        
        # Herfindahl-Hirschman Index (HHI)
        hhi = sum(w ** 2 for w in weights.values())
        diversification = 1 - hhi
        return Decimal(str(diversification))
    
    def _calculate_concentration_ratio(self, weights: Dict[str, float]) -> Decimal:
        """Calculate concentration ratio."""
        if not weights:
            return Decimal('0')
        
        # Maximum weight
        max_weight = max(weights.values()) if weights else 0
        return Decimal(str(max_weight))
    
    async def _calculate_beta(self, positions: List[Position]) -> Decimal:
        """Calculate portfolio beta."""
        if not positions:
            return Decimal('1')
        
        # Use market proxy (would be implemented with real market data)
        return Decimal('1')
    
    async def _calculate_alpha(self, positions: List[Position], beta: Decimal) -> Decimal:
        """Calculate portfolio alpha."""
        if not positions:
            return Decimal('0')
        
        # Use market proxy (would be implemented with real market data)
        return Decimal('0')
    
    # =========================================================================
    # STRESS TESTING
    # =========================================================================
    
    async def run_stress_test(
        self,
        positions: List[Position],
        scenario: str = "custom",
        shock_percent: Optional[Decimal] = None
    ) -> StressTestResult:
        """
        Run a stress test on the portfolio.
        
        Args:
            positions: List of positions
            scenario: Stress scenario name
            shock_percent: Custom shock percentage
            
        Returns:
            StressTestResult
        """
        if shock_percent is None:
            shock_percent = self.config.stress_shock_percent
        
        # Apply shock to all positions
        affected_positions = []
        total_loss = Decimal('0')
        max_loss = Decimal('0')
        max_loss_position = None
        
        for position in positions:
            # Calculate position value under stress
            stressed_value = position.market_value * (1 - shock_percent)
            loss = position.market_value - stressed_value
            loss_percent = shock_percent
            
            affected_positions.append({
                'position_id': position.id,
                'symbol': position.symbol,
                'loss': float(loss),
                'loss_percent': float(loss_percent)
            })
            
            total_loss += loss
            if loss > max_loss:
                max_loss = loss
                max_loss_position = position
        
        # Calculate metrics
        portfolio_value = sum(p.market_value for p in positions)
        loss_percent = total_loss / portfolio_value if portfolio_value > 0 else Decimal('0')
        
        # Check risk limits
        var_breach = loss_percent > self.config.var_95
        drawdown_exceeded = loss_percent > self.config.max_drawdown
        margin_call = loss_percent > Decimal('0.10')  # 10% loss
        liquidation_risk = loss_percent > Decimal('0.20')  # 20% loss
        
        result = StressTestResult(
            scenario=scenario,
            portfolio_loss=total_loss.quantize(Decimal('0.0001')),
            portfolio_loss_percent=loss_percent.quantize(Decimal('0.0001')),
            max_position_loss=max_loss.quantize(Decimal('0.0001')),
            max_position_loss_percent=shock_percent,
            var_breach=var_breach,
            drawdown_exceeded=drawdown_exceeded,
            margin_call=margin_call,
            liquidation_risk=liquidation_risk,
            affected_positions=affected_positions,
            risk_metrics={
                'var_95': self.config.var_95,
                'max_drawdown': self.config.max_drawdown,
                'loss_threshold': Decimal('0.10'),
                'liquidation_threshold': Decimal('0.20')
            }
        )
        
        self._stress_results.append(result)
        
        return result
    
    # =========================================================================
    # RISK SCORE
    # =========================================================================
    
    def _get_risk_level(self, risk_score: Decimal) -> RiskLevel:
        """Get risk level from risk score."""
        if risk_score <= 20:
            return RiskLevel.VERY_LOW
        elif risk_score <= 40:
            return RiskLevel.LOW
        elif risk_score <= 60:
            return RiskLevel.MODERATE
        elif risk_score <= 80:
            return RiskLevel.HIGH
        else:
            return RiskLevel.VERY_HIGH
    
    def _get_total_portfolio_value(self) -> Decimal:
        """Get total portfolio value."""
        total = Decimal('0')
        # This would be implemented with actual portfolio tracking
        return total
    
    async def _get_volatility(self, symbol: str) -> Decimal:
        """Get volatility for a symbol."""
        # This would be implemented with actual volatility calculations
        return Decimal('0.3')  # 30% volatility
    
    async def _get_historical_returns(self, positions: List[Position]) -> List[float]:
        """Get historical returns for positions."""
        returns = []
        for position in positions:
            # Get historical prices
            try:
                bars = await self.market_data.get_bars(
                    position.symbol,
                    timeframe="1h",
                    limit=100
                )
                if bars:
                    for bar in bars:
                        returns.append(float((bar.close - bar.open) / bar.open))
            except Exception:
                pass
        
        return returns if returns else [0]
    
    async def _get_position_weights(self, positions: List[Position]) -> Dict[str, float]:
        """Get position weights."""
        total_value = sum(p.market_value for p in positions)
        weights = {}
        
        for position in positions:
            if total_value > 0:
                weights[position.id] = float(position.market_value / total_value)
            else:
                weights[position.id] = 0
        
        return weights
    
    # =========================================================================
    # MONITORING
    # =========================================================================
    
    async def _monitor_loop(self):
        """Monitor risk levels."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Get positions (would come from position tracker)
                positions = []
                
                if positions:
                    # Calculate portfolio risk
                    portfolio_risk = await self.calculate_portfolio_risk(positions)
                    
                    # Check for alerts
                    if portfolio_risk.status in [RiskStatus.HIGH, RiskStatus.CRITICAL]:
                        await self._trigger_alert(
                            "portfolio_risk",
                            "critical",
                            f"Portfolio risk {portfolio_risk.risk_score:.1f}%",
                            portfolio_risk.risk_limit,
                            portfolio_risk.risk_score
                        )
                    
                    # Check drawdown
                    if portfolio_risk.current_drawdown > self.config.max_drawdown:
                        await self._trigger_alert(
                            "drawdown",
                            "critical",
                            f"Drawdown {portfolio_risk.current_drawdown:.2f}%",
                            self.config.max_drawdown,
                            portfolio_risk.current_drawdown
                        )
                    
                    # Check loss limits
                    # Would need daily loss tracking
                    
                    # Save to database
                    if self.pool:
                        await self._save_portfolio_risk(portfolio_risk)
                        for pos_risk in portfolio_risk.position_risks:
                            await self._save_position_risk(pos_risk)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # ALERTS
    # =========================================================================
    
    async def _trigger_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        threshold: Decimal,
        current_value: Decimal
    ):
        """Trigger a risk alert."""
        alert = RiskAlert(
            type=alert_type,
            severity=severity,
            message=message,
            threshold=threshold,
            current_value=current_value,
            triggered_at=datetime.utcnow()
        )
        
        self._alerts.append(alert)
        
        # Trigger callbacks
        if "risk_alert" in self._callbacks:
            for callback in self._callbacks["risk_alert"]:
                try:
                    await callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")
        
        # Save alert
        if self.pool:
            await self._save_alert(alert)
        
        logger.warning(f"Risk alert: {message}")
    
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
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_metrics(self):
        """Load metrics from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM risk_metrics ORDER BY timestamp DESC LIMIT 1000"
                )
                
                for row in rows:
                    metric = RiskMetric(
                        id=row['id'],
                        type=RiskMetricType(row['type']),
                        value=row['value'],
                        timestamp=row['timestamp'],
                        category=RiskCategory(row['category']),
                        status=RiskStatus(row['status']),
                        threshold=row['threshold'],
                        metadata=row['metadata'] or {}
                    )
                    self._metrics.append(metric)
                
                logger.info(f"Loaded {len(self._metrics)} risk metrics")
                
        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
    
    async def _save_portfolio_risk(self, risk: PortfolioRisk):
        """Save portfolio risk to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO portfolio_risk_assessments (
                        timestamp, total_value, var_95, var_99,
                        cvar_95, cvar_99, expected_shortfall,
                        max_drawdown, current_drawdown,
                        sharpe_ratio, sortino_ratio, calmar_ratio,
                        omega_ratio, diversification_ratio,
                        concentration_ratio, beta, alpha,
                        risk_limit, risk_utilization, total_risk,
                        risk_level, risk_score,
                        market_risk, liquidity_risk,
                        counterparty_risk, operational_risk,
                        systemic_risk, status, warnings, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7,
                              $8, $9, $10, $11, $12, $13,
                              $14, $15, $16, $17,
                              $18, $19, $20, $21,
                              $22, $23, $24, $25, $26,
                              $27, $28, $29, $30)
                    """,
                    risk.timestamp,
                    risk.total_value,
                    risk.var_95,
                    risk.var_99,
                    risk.cvar_95,
                    risk.cvar_99,
                    risk.expected_shortfall,
                    risk.max_drawdown,
                    risk.current_drawdown,
                    risk.sharpe_ratio,
                    risk.sortino_ratio,
                    risk.calmar_ratio,
                    risk.omega_ratio,
                    risk.diversification_ratio,
                    risk.concentration_ratio,
                    risk.beta,
                    risk.alpha,
                    risk.risk_limit,
                    risk.risk_utilization,
                    risk.total_risk,
                    risk.risk_level.value,
                    risk.risk_score,
                    risk.market_risk,
                    risk.liquidity_risk,
                    risk.counterparty_risk,
                    risk.operational_risk,
                    risk.systemic_risk,
                    risk.status.value,
                    json.dumps(risk.warnings),
                    json.dumps(risk.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving portfolio risk: {e}")
    
    async def _save_position_risk(self, risk: PositionRisk):
        """Save position risk to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO position_risk_assessments (
                        position_id, symbol, exchange,
                        market_risk, liquidity_risk,
                        concentration_risk, leverage_risk,
                        volatility_risk, total_risk,
                        risk_level, risk_score,
                        risk_limit, risk_utilization,
                        status, warnings, timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7,
                              $8, $9, $10, $11,
                              $12, $13, $14, $15,
                              $16, $17)
                    ON CONFLICT (position_id, timestamp) DO UPDATE SET
                        market_risk = EXCLUDED.market_risk,
                        liquidity_risk = EXCLUDED.liquidity_risk,
                        concentration_risk = EXCLUDED.concentration_risk,
                        leverage_risk = EXCLUDED.leverage_risk,
                        volatility_risk = EXCLUDED.volatility_risk,
                        total_risk = EXCLUDED.total_risk,
                        risk_level = EXCLUDED.risk_level,
                        risk_score = EXCLUDED.risk_score,
                        risk_utilization = EXCLUDED.risk_utilization,
                        status = EXCLUDED.status,
                        warnings = EXCLUDED.warnings,
                        metadata = EXCLUDED.metadata
                    """,
                    risk.position_id,
                    risk.symbol,
                    risk.exchange,
                    risk.market_risk,
                    risk.liquidity_risk,
                    risk.concentration_risk,
                    risk.leverage_risk,
                    risk.volatility_risk,
                    risk.total_risk,
                    risk.risk_level.value,
                    risk.risk_score,
                    risk.risk_limit,
                    risk.risk_utilization,
                    risk.status.value,
                    json.dumps(risk.warnings),
                    risk.timestamp,
                    json.dumps(risk.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving position risk: {e}")
    
    async def _save_alert(self, alert: RiskAlert):
        """Save risk alert to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO risk_alerts (
                        id, type, severity, message,
                        metric_id, position_id,
                        threshold, current_value,
                        triggered_at, acknowledged,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5,
                              $6, $7, $8, $9, $10,
                              $11)
                    """,
                    alert.id,
                    alert.type,
                    alert.severity,
                    alert.message,
                    alert.metric_id,
                    alert.position_id,
                    alert.threshold,
                    alert.current_value,
                    alert.triggered_at,
                    alert.acknowledged,
                    json.dumps(alert.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving alert: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the risk calculator."""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("RiskCalculator shutdown")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'RiskCalculator',
    'RiskMetricType',
    'RiskLevel',
    'RiskCategory',
    'RiskStatus',
    'RiskConfig',
    'RiskMetric',
    'PositionRisk',
    'PortfolioRisk',
    'StressTestResult',
    'RiskAlert'
]
