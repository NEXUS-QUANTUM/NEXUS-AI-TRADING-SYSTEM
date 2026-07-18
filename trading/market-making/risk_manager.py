"""
NEXUS AI TRADING SYSTEM - Market Making Risk Manager Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/market-making/risk_manager.py
Description: Comprehensive risk management for market making with full API integration
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.market_making_config import MarketMakingConfig
from shared.configs.risk_config import RiskConfig
from shared.constants.trading_constants import (
    RISK_LEVELS,
    ORDER_TYPES,
    POSITION_DIRECTIONS
)
from shared.helpers.trading_helpers import (
    calculate_var,
    calculate_cvar,
    calculate_drawdown,
    calculate_sharpe_ratio
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Position, Order, Trade
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.order_repository import OrderRepository
from backend.database.repositories.trade_repository import TradeRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Market making imports
from trading.market_making.base import BaseMarketMaker
from trading.market_making.analytics import MarketMakingAnalytics

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class RiskLimitType(str, Enum):
    """Types of risk limits"""
    POSITION_SIZE = "position_size"
    POSITION_VALUE = "position_value"
    EXPOSURE = "exposure"
    DRAWDOWN = "drawdown"
    DAILY_LOSS = "daily_loss"
    WEEKLY_LOSS = "weekly_loss"
    MONTHLY_LOSS = "monthly_loss"
    VAR = "var"
    CVAR = "cvar"
    LEVERAGE = "leverage"
    CONCENTRATION = "concentration"
    ORDER_SIZE = "order_size"
    ORDER_FREQUENCY = "order_frequency"
    TRADE_FREQUENCY = "trade_frequency"
    SPREAD = "spread"
    VOLATILITY = "volatility"


class RiskLevel(str, Enum):
    """Risk levels"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class RiskAction(str, Enum):
    """Actions to take on risk breach"""
    NONE = "none"
    LOG = "log"
    NOTIFY = "notify"
    REDUCE_SIZE = "reduce_size"
    PAUSE = "pause"
    STOP = "stop"
    LIQUIDATE = "liquidate"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RiskLimitConfig(BaseModel):
    """Configuration for a risk limit"""
    limit_type: RiskLimitType
    max_value: Optional[float] = None
    min_value: Optional[float] = None
    current_value: Optional[float] = None
    risk_level: RiskLevel = RiskLevel.MODERATE
    action: RiskAction = RiskAction.NOTIFY
    enabled: bool = True
    cooldown_seconds: int = 300
    notification_channels: List[str] = ["email", "telegram"]
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('max_value')
    def validate_max(cls, v, values):
        if v is not None and v < 0:
            raise ValueError("max_value must be non-negative")
        return v

    @validator('min_value')
    def validate_min(cls, v, values):
        if v is not None and v < 0:
            raise ValueError("min_value must be non-negative")
        return v


class RiskMetricsRequest(BaseModel):
    """Request model for risk metrics"""
    symbol: str
    lookback_period: int = 100
    confidence_level: float = 0.95
    time_horizon: str = "1d"
    include_positions: bool = True
    include_trades: bool = True
    include_orders: bool = True


class RiskMetricsResponse(BaseModel):
    """Response model for risk metrics"""
    symbol: str
    timestamp: datetime
    position_risk: Dict[str, Any]
    market_risk: Dict[str, Any]
    liquidity_risk: Dict[str, Any]
    operational_risk: Dict[str, Any]
    composite_risk_score: float
    risk_level: RiskLevel
    breaches: List[Dict[str, Any]]
    warnings: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskBreachResponse(BaseModel):
    """Response model for risk breach"""
    breach_id: str
    symbol: str
    limit_type: RiskLimitType
    current_value: float
    limit_value: float
    risk_level: RiskLevel
    action_taken: RiskAction
    timestamp: datetime
    resolved: bool
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RiskContext:
    """Context for risk calculations"""
    symbol: str
    positions: List[Any]
    trades: List[Any]
    orders: List[Any]
    market_data: Dict[str, Any]
    current_price: float
    total_exposure: float
    total_value: float
    daily_pnl: float
    weekly_pnl: float
    monthly_pnl: float
    current_drawdown: float
    volatility: float
    timestamp: datetime


@dataclass
class RiskLimitState:
    """State of a risk limit"""
    limit_type: RiskLimitType
    current_value: float
    limit_value: float
    is_breached: bool
    breach_count: int
    last_breach: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# MARKET MAKING RISK MANAGER
# =============================================================================

class MarketMakingRiskManager:
    """
    Comprehensive Risk Manager for Market Making with full API integration.
    
    Features:
    - Real-time risk monitoring
    - Multiple risk limit types
    - Automated risk actions
    - Position risk management
    - Market risk assessment
    - Liquidity risk monitoring
    - Operational risk tracking
    - Risk reporting
    - Breach handling
    - Cooldown management
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        market_making_config: Optional[MarketMakingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        analytics: Optional[MarketMakingAnalytics] = None
    ):
        """
        Initialize MarketMakingRiskManager.
        
        Args:
            config: Risk configuration
            market_making_config: Market making configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            order_repo: Order repository
            trade_repo: Trade repository
            analytics: Market making analytics
        """
        self.config = config or RiskConfig()
        self.mm_config = market_making_config or MarketMakingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.analytics = analytics or MarketMakingAnalytics()
        
        # Risk limits
        self._limits: Dict[str, RiskLimitConfig] = {}
        self._limit_states: Dict[str, RiskLimitState] = {}
        self._breaches: List[RiskBreachResponse] = []
        
        # Monitoring
        self._is_monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Initialize limits
        self._init_default_limits()
        
        logger.info("MarketMakingRiskManager initialized")

    def _init_default_limits(self) -> None:
        """Initialize default risk limits"""
        default_limits = {
            RiskLimitType.POSITION_SIZE: {
                'max_value': 100.0,
                'risk_level': RiskLevel.HIGH,
                'action': RiskAction.PAUSE
            },
            RiskLimitType.POSITION_VALUE: {
                'max_value': 10000.0,
                'risk_level': RiskLevel.HIGH,
                'action': RiskAction.PAUSE
            },
            RiskLimitType.EXPOSURE: {
                'max_value': 50000.0,
                'risk_level': RiskLevel.HIGH,
                'action': RiskAction.PAUSE
            },
            RiskLimitType.DRAWDOWN: {
                'max_value': 0.10,  # 10%
                'risk_level': RiskLevel.CRITICAL,
                'action': RiskAction.STOP
            },
            RiskLimitType.DAILY_LOSS: {
                'max_value': 1000.0,
                'risk_level': RiskLevel.CRITICAL,
                'action': RiskAction.STOP
            },
            RiskLimitType.WEEKLY_LOSS: {
                'max_value': 3000.0,
                'risk_level': RiskLevel.CRITICAL,
                'action': RiskAction.STOP
            },
            RiskLimitType.VAR: {
                'max_value': 0.02,  # 2%
                'risk_level': RiskLevel.HIGH,
                'action': RiskAction.REDUCE_SIZE
            },
            RiskLimitType.CVAR: {
                'max_value': 0.03,  # 3%
                'risk_level': RiskLevel.CRITICAL,
                'action': RiskAction.PAUSE
            },
            RiskLimitType.LEVERAGE: {
                'max_value': 2.0,
                'risk_level': RiskLevel.HIGH,
                'action': RiskAction.REDUCE_SIZE
            },
            RiskLimitType.CONCENTRATION: {
                'max_value': 0.40,  # 40%
                'risk_level': RiskLevel.HIGH,
                'action': RiskAction.NOTIFY
            },
            RiskLimitType.ORDER_SIZE: {
                'max_value': 10.0,
                'risk_level': RiskLevel.MODERATE,
                'action': RiskAction.NOTIFY
            },
            RiskLimitType.SPREAD: {
                'max_value': 0.05,
                'risk_level': RiskLevel.MODERATE,
                'action': RiskAction.NOTIFY
            },
            RiskLimitType.VOLATILITY: {
                'max_value': 0.03,
                'risk_level': RiskLevel.HIGH,
                'action': RiskAction.PAUSE
            }
        }
        
        for limit_type, params in default_limits.items():
            self._limits[limit_type.value] = RiskLimitConfig(
                limit_type=limit_type,
                max_value=params['max_value'],
                risk_level=params['risk_level'],
                action=params['action']
            )
            self._limit_states[limit_type.value] = RiskLimitState(
                limit_type=limit_type,
                current_value=0,
                limit_value=params['max_value'],
                is_breached=False,
                breach_count=0
            )

    # =========================================================================
    # Risk Metrics
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_risk_metrics(
        self,
        request: RiskMetricsRequest
    ) -> RiskMetricsResponse:
        """
        Get comprehensive risk metrics.
        
        Args:
            request: Risk metrics request
            
        Returns:
            RiskMetricsResponse: Risk metrics
        """
        try:
            # Build context
            context = await self._build_context(request)
            
            # Calculate risk metrics
            position_risk = await self._calculate_position_risk(context)
            market_risk = await self._calculate_market_risk(context)
            liquidity_risk = await self._calculate_liquidity_risk(context)
            operational_risk = await self._calculate_operational_risk(context)
            
            # Calculate composite risk score
            composite_score = self._calculate_composite_risk_score(
                position_risk,
                market_risk,
                liquidity_risk,
                operational_risk
            )
            
            # Determine risk level
            risk_level = self._determine_risk_level(composite_score)
            
            # Check breaches
            breaches = await self._check_limits(context)
            
            # Generate warnings
            warnings = await self._generate_warnings(context, breaches)
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                context,
                breaches,
                composite_score
            )
            
            return RiskMetricsResponse(
                symbol=request.symbol,
                timestamp=datetime.utcnow(),
                position_risk=position_risk,
                market_risk=market_risk,
                liquidity_risk=liquidity_risk,
                operational_risk=operational_risk,
                composite_risk_score=composite_score,
                risk_level=risk_level,
                breaches=breaches,
                warnings=warnings,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error getting risk metrics: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Risk metrics calculation failed: {str(e)}"
            )

    async def _build_context(self, request: RiskMetricsRequest) -> RiskContext:
        """Build risk context"""
        # Get positions
        positions = await self.position_repo.get_by_symbol(request.symbol)
        
        # Get trades
        trades = await self.trade_repo.get_by_symbol(
            request.symbol,
            limit=request.lookback_period
        )
        
        # Get orders
        orders = await self.order_repo.get_by_symbol(request.symbol)
        
        # Get market data
        market_data = await self._get_market_data(request.symbol)
        current_price = market_data.get('price', 0)
        
        # Calculate exposure and value
        total_exposure = sum(abs(p.size) * p.entry_price for p in positions)
        total_value = sum(p.size * p.entry_price for p in positions)
        
        # Calculate PnL
        daily_pnl = await self._calculate_pnl(trades, period='daily')
        weekly_pnl = await self._calculate_pnl(trades, period='weekly')
        monthly_pnl = await self._calculate_pnl(trades, period='monthly')
        
        # Calculate drawdown
        current_drawdown = await self._calculate_drawdown(trades)
        
        # Get volatility
        volatility = market_data.get('volatility', 0.02)
        
        return RiskContext(
            symbol=request.symbol,
            positions=positions,
            trades=trades,
            orders=orders,
            market_data=market_data,
            current_price=current_price,
            total_exposure=total_exposure,
            total_value=total_value,
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            monthly_pnl=monthly_pnl,
            current_drawdown=current_drawdown,
            volatility=volatility,
            timestamp=datetime.utcnow()
        )

    async def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    ticker = await broker.get_ticker(symbol)
                    return {
                        'price': float(ticker.get('price', 0)),
                        'bid': float(ticker.get('bid', 0)),
                        'ask': float(ticker.get('ask', 0)),
                        'volume': float(ticker.get('volume', 0)),
                        'volatility': float(ticker.get('volatility', 0.02)),
                        'high': float(ticker.get('high', 0)),
                        'low': float(ticker.get('low', 0))
                    }
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting market data: {e}")
        
        return {'price': 100.0, 'volatility': 0.02}

    async def _calculate_pnl(
        self,
        trades: List[Any],
        period: str = 'daily'
    ) -> float:
        """Calculate PnL for period"""
        if not trades:
            return 0
        
        now = datetime.utcnow()
        
        if period == 'daily':
            cutoff = now - timedelta(days=1)
        elif period == 'weekly':
            cutoff = now - timedelta(days=7)
        elif period == 'monthly':
            cutoff = now - timedelta(days=30)
        else:
            cutoff = now - timedelta(days=1)
        
        period_trades = [t for t in trades if t.execution_time >= cutoff]
        return sum(t.pnl for t in period_trades)

    async def _calculate_drawdown(self, trades: List[Any]) -> float:
        """Calculate current drawdown"""
        if not trades:
            return 0
        
        equity = [0]
        for trade in trades:
            equity.append(equity[-1] + trade.pnl)
        
        peak = max(equity)
        current = equity[-1]
        
        if peak == 0:
            return 0
        
        return (peak - current) / peak

    # =========================================================================
    # Risk Calculations
    # =========================================================================

    async def _calculate_position_risk(
        self,
        context: RiskContext
    ) -> Dict[str, Any]:
        """Calculate position risk metrics"""
        metrics = {}
        
        if context.positions:
            # Position size
            total_size = sum(abs(p.size) for p in context.positions)
            metrics['total_size'] = total_size
            
            # Position value
            total_value = sum(p.size * p.entry_price for p in context.positions)
            metrics['total_value'] = total_value
            
            # Average position
            metrics['avg_position'] = total_size / len(context.positions) if context.positions else 0
            metrics['max_position'] = max(abs(p.size) for p in context.positions) if context.positions else 0
            
            # Position concentration
            if total_size > 0:
                max_ratio = max(abs(p.size) / total_size for p in context.positions)
                metrics['concentration'] = max_ratio
            else:
                metrics['concentration'] = 0
            
            # Unrealized PnL
            unrealized = 0
            for pos in context.positions:
                if hasattr(pos, 'current_price'):
                    pnl = (pos.current_price - pos.entry_price) * pos.size
                    unrealized += pnl
            metrics['unrealized_pnl'] = unrealized
        
        return metrics

    async def _calculate_market_risk(
        self,
        context: RiskContext
    ) -> Dict[str, Any]:
        """Calculate market risk metrics"""
        metrics = {
            'volatility': context.volatility,
            'current_price': context.current_price,
            'daily_pnl': context.daily_pnl,
            'weekly_pnl': context.weekly_pnl,
            'monthly_pnl': context.monthly_pnl,
            'current_drawdown': context.current_drawdown
        }
        
        # Calculate VaR and CVaR from trades
        if context.trades and len(context.trades) > 30:
            returns = [t.pnl for t in context.trades]
            
            # VaR at 95%
            var_95 = np.percentile(returns, 5)
            metrics['var_95'] = var_95
            
            # CVaR at 95%
            cvar_95 = np.mean([r for r in returns if r <= var_95])
            metrics['cvar_95'] = cvar_95
            
            # Sharpe ratio
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                metrics['sharpe_ratio'] = avg_return / std_return * np.sqrt(252)
            else:
                metrics['sharpe_ratio'] = 0
        
        return metrics

    async def _calculate_liquidity_risk(
        self,
        context: RiskContext
    ) -> Dict[str, Any]:
        """Calculate liquidity risk metrics"""
        metrics = {}
        
        # Order fill rate
        if context.orders:
            filled = [o for o in context.orders if o.status == 'filled']
            metrics['fill_rate'] = len(filled) / len(context.orders) if context.orders else 0
        
        # Order book depth
        if context.market_data:
            bid_depth = context.market_data.get('bid_depth', 0)
            ask_depth = context.market_data.get('ask_depth', 0)
            metrics['bid_depth'] = bid_depth
            metrics['ask_depth'] = ask_depth
            metrics['total_depth'] = bid_depth + ask_depth
        
        # Spread
        spread = context.market_data.get('ask', 0) - context.market_data.get('bid', 0)
        metrics['current_spread'] = spread
        
        # Liquidity score
        if context.orders and context.market_data:
            depth = metrics.get('total_depth', 0)
            fill_rate = metrics.get('fill_rate', 0)
            spread_score = 1 - min(spread / 0.05, 1) if spread > 0 else 1
            
            metrics['liquidity_score'] = (
                depth / 10000 * 0.4 +
                fill_rate * 0.3 +
                spread_score * 0.3
            )
        
        return metrics

    async def _calculate_operational_risk(
        self,
        context: RiskContext
    ) -> Dict[str, Any]:
        """Calculate operational risk metrics"""
        metrics = {}
        
        # Order frequency
        if context.orders and len(context.orders) > 1:
            first = min(o.created_at for o in context.orders)
            last = max(o.created_at for o in context.orders)
            duration = (last - first).total_seconds()
            if duration > 0:
                metrics['order_frequency'] = len(context.orders) / duration
            else:
                metrics['order_frequency'] = 0
        
        # Trade frequency
        if context.trades and len(context.trades) > 1:
            first = min(t.execution_time for t in context.trades)
            last = max(t.execution_time for t in context.trades)
            duration = (last - first).total_seconds()
            if duration > 0:
                metrics['trade_frequency'] = len(context.trades) / duration
            else:
                metrics['trade_frequency'] = 0
        
        # Cancellation rate
        if context.orders:
            cancelled = [o for o in context.orders if o.status == 'cancelled']
            metrics['cancellation_rate'] = len(cancelled) / len(context.orders) if context.orders else 0
        
        # Error rate
        if context.orders:
            rejected = [o for o in context.orders if o.status == 'rejected']
            metrics['error_rate'] = len(rejected) / len(context.orders) if context.orders else 0
        
        return metrics

    def _calculate_composite_risk_score(
        self,
        position_risk: Dict[str, Any],
        market_risk: Dict[str, Any],
        liquidity_risk: Dict[str, Any],
        operational_risk: Dict[str, Any]
    ) -> float:
        """Calculate composite risk score (0-100)"""
        score = 0
        
        # Position risk contribution (max 35)
        concentration = position_risk.get('concentration', 0)
        score += min(concentration * 40, 20)
        
        position_ratio = position_risk.get('max_position', 0) / 100 if position_risk.get('max_position', 0) > 0 else 0
        score += min(position_ratio * 15, 15)
        
        # Market risk contribution (max 35)
        drawdown = market_risk.get('current_drawdown', 0)
        score += min(drawdown * 100, 15)
        
        volatility = market_risk.get('volatility', 0)
        score += min(volatility * 200, 10)
        
        var_95 = market_risk.get('var_95', 0)
        if var_95 < 0:
            score += min(abs(var_95) * 5, 10)
        
        # Liquidity risk contribution (max 20)
        fill_rate = liquidity_risk.get('fill_rate', 1)
        if fill_rate > 0:
            score += min((1 - fill_rate) * 10, 10)
        
        spread = liquidity_risk.get('current_spread', 0)
        if spread > 0:
            score += min(spread * 200, 10)
        
        # Operational risk contribution (max 10)
        cancellation_rate = operational_risk.get('cancellation_rate', 0)
        score += min(cancellation_rate * 10, 5)
        
        error_rate = operational_risk.get('error_rate', 0)
        score += min(error_rate * 10, 5)
        
        return min(max(score, 0), 100)

    def _determine_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level from score"""
        if score < 20:
            return RiskLevel.LOW
        elif score < 40:
            return RiskLevel.MODERATE
        elif score < 60:
            return RiskLevel.HIGH
        elif score < 80:
            return RiskLevel.CRITICAL
        else:
            return RiskLevel.EMERGENCY

    # =========================================================================
    # Risk Limits
    # =========================================================================

    async def _check_limits(
        self,
        context: RiskContext
    ) -> List[Dict[str, Any]]:
        """Check all risk limits"""
        breaches = []
        
        for limit_type, config in self._limits.items():
            if not config.enabled:
                continue
            
            # Get current value
            current_value = await self._get_limit_value(limit_type, context)
            
            if current_value is None:
                continue
            
            # Update state
            state = self._limit_states[limit_type]
            state.current_value = current_value
            
            # Check if breached
            is_breached = False
            
            if config.max_value is not None and current_value > config.max_value:
                is_breached = True
            elif config.min_value is not None and current_value < config.min_value:
                is_breached = True
            
            if is_breached:
                # Check cooldown
                if state.cooldown_until and datetime.utcnow() < state.cooldown_until:
                    continue
                
                state.is_breached = True
                state.breach_count += 1
                state.last_breach = datetime.utcnow()
                
                # Set cooldown
                state.cooldown_until = datetime.utcnow() + timedelta(
                    seconds=config.cooldown_seconds
                )
                
                # Create breach record
                breach = {
                    'limit_type': limit_type,
                    'current_value': current_value,
                    'limit_value': config.max_value or config.min_value or 0,
                    'risk_level': config.risk_level.value,
                    'action_taken': config.action.value,
                    'timestamp': datetime.utcnow()
                }
                breaches.append(breach)
                
                # Execute action
                await self._execute_action(config, breach)
                
                # Log breach
                logger.warning(
                    f"Risk limit breached: {limit_type} - "
                    f"Current: {current_value}, Limit: {config.max_value}"
                )
            
            self._limit_states[limit_type] = state
        
        return breaches

    async def _get_limit_value(
        self,
        limit_type: str,
        context: RiskContext
    ) -> Optional[float]:
        """Get current value for limit type"""
        mapping = {
            RiskLimitType.POSITION_SIZE: context.total_exposure,
            RiskLimitType.POSITION_VALUE: context.total_value,
            RiskLimitType.EXPOSURE: context.total_exposure,
            RiskLimitType.DRAWDOWN: context.current_drawdown,
            RiskLimitType.DAILY_LOSS: abs(context.daily_pnl),
            RiskLimitType.WEEKLY_LOSS: abs(context.weekly_pnl),
            RiskLimitType.MONTHLY_LOSS: abs(context.monthly_pnl),
            RiskLimitType.VOLATILITY: context.volatility
        }
        
        limit_enum = RiskLimitType(limit_type) if limit_type in RiskLimitType.__members__ else None
        
        if limit_enum in mapping:
            return mapping[limit_enum]
        
        # For other limits, calculate
        if limit_enum == RiskLimitType.VAR:
            return await self._calculate_var(context)
        elif limit_enum == RiskLimitType.CVAR:
            return await self._calculate_cvar(context)
        elif limit_enum == RiskLimitType.CONCENTRATION:
            return await self._calculate_concentration(context)
        elif limit_enum == RiskLimitType.SPREAD:
            return context.market_data.get('ask', 0) - context.market_data.get('bid', 0)
        
        return None

    async def _calculate_var(self, context: RiskContext) -> float:
        """Calculate VaR"""
        if not context.trades or len(context.trades) < 30:
            return 0
        
        returns = [t.pnl for t in context.trades]
        return abs(np.percentile(returns, 5))

    async def _calculate_cvar(self, context: RiskContext) -> float:
        """Calculate CVaR"""
        if not context.trades or len(context.trades) < 30:
            return 0
        
        returns = [t.pnl for t in context.trades]
        var = np.percentile(returns, 5)
        cvar = np.mean([r for r in returns if r <= var])
        return abs(cvar)

    async def _calculate_concentration(self, context: RiskContext) -> float:
        """Calculate concentration"""
        if not context.positions:
            return 0
        
        total_size = sum(abs(p.size) for p in context.positions)
        if total_size == 0:
            return 0
        
        max_size = max(abs(p.size) for p in context.positions)
        return max_size / total_size

    async def _execute_action(
        self,
        config: RiskLimitConfig,
        breach: Dict[str, Any]
    ) -> None:
        """Execute risk action"""
        try:
            if config.action == RiskAction.NONE:
                pass
            elif config.action == RiskAction.LOG:
                logger.info(f"Risk breach logged: {breach}")
            elif config.action == RiskAction.NOTIFY:
                await self._send_notification(config, breach)
            elif config.action == RiskAction.REDUCE_SIZE:
                await self._reduce_position_size(config)
            elif config.action == RiskAction.PAUSE:
                await self._pause_market_making(config)
            elif config.action == RiskAction.STOP:
                await self._stop_market_making(config)
            elif config.action == RiskAction.LIQUIDATE:
                await self._liquidate_positions(config)
        except Exception as e:
            logger.error(f"Error executing action {config.action}: {e}")

    async def _send_notification(
        self,
        config: RiskLimitConfig,
        breach: Dict[str, Any]
    ) -> None:
        """Send notification"""
        message = (
            f"⚠️ Risk Limit Breach\n"
            f"Limit: {breach['limit_type']}\n"
            f"Current Value: {breach['current_value']:.2f}\n"
            f"Limit Value: {breach['limit_value']:.2f}\n"
            f"Risk Level: {breach['risk_level']}\n"
            f"Action: {breach['action_taken']}"
        )
        
        for channel in config.notification_channels:
            try:
                if channel == "email":
                    # Send email
                    pass
                elif channel == "telegram":
                    # Send Telegram
                    pass
                elif channel == "slack":
                    # Send Slack
                    pass
            except Exception as e:
                logger.error(f"Error sending notification via {channel}: {e}")

    async def _reduce_position_size(self, config: RiskLimitConfig) -> None:
        """Reduce position size"""
        logger.info(f"Reducing position size due to {config.limit_type.value} breach")
        # Implementation would reduce positions

    async def _pause_market_making(self, config: RiskLimitConfig) -> None:
        """Pause market making"""
        logger.info(f"Pausing market making due to {config.limit_type.value} breach")
        # Implementation would pause market making

    async def _stop_market_making(self, config: RiskLimitConfig) -> None:
        """Stop market making"""
        logger.info(f"Stopping market making due to {config.limit_type.value} breach")
        # Implementation would stop market making

    async def _liquidate_positions(self, config: RiskLimitConfig) -> None:
        """Liquidate positions"""
        logger.info(f"Liquidating positions due to {config.limit_type.value} breach")
        # Implementation would liquidate positions

    # =========================================================================
    # Warnings and Recommendations
    # =========================================================================

    async def _generate_warnings(
        self,
        context: RiskContext,
        breaches: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate warnings"""
        warnings = []
        
        if breaches:
            warnings.append(f"{len(breaches)} risk limit(s) breached")
        
        if context.current_drawdown > 0.05:
            warnings.append(f"Drawdown at {context.current_drawdown*100:.1f}%")
        
        if context.volatility > 0.03:
            warnings.append(f"High volatility: {context.volatility*100:.1f}%")
        
        if context.daily_pnl < -500:
            warnings.append(f"Significant daily loss: ${context.daily_pnl:.2f}")
        
        return warnings

    async def _generate_recommendations(
        self,
        context: RiskContext,
        breaches: List[Dict[str, Any]],
        score: float
    ) -> List[str]:
        """Generate recommendations"""
        recommendations = []
        
        if score > 70:
            recommendations.append("Critical risk level. Immediate action required.")
        
        if breaches:
            recommendations.append(f"Address {len(breaches)} risk limit breaches")
        
        if context.current_drawdown > 0.08:
            recommendations.append("High drawdown. Consider reducing position size.")
        
        if context.daily_pnl < -1000:
            recommendations.append("Daily loss limit approached. Reduce risk exposure.")
        
        if context.volatility > 0.04:
            recommendations.append("Extreme volatility. Consider widening spreads.")
        
        if not recommendations:
            recommendations.append("All risk metrics are within acceptable ranges.")
        
        return recommendations

    # =========================================================================
    # Limit Management API
    # =========================================================================

    async def add_limit(self, config: RiskLimitConfig) -> bool:
        """Add a risk limit"""
        try:
            self._limits[config.limit_type.value] = config
            self._limit_states[config.limit_type.value] = RiskLimitState(
                limit_type=config.limit_type,
                current_value=0,
                limit_value=config.max_value or config.min_value or 0,
                is_breached=False,
                breach_count=0
            )
            logger.info(f"Added risk limit: {config.limit_type.value}")
            return True
        except Exception as e:
            logger.error(f"Error adding limit: {e}")
            return False

    async def update_limit(
        self,
        limit_type: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update a risk limit"""
        try:
            if limit_type not in self._limits:
                return False
            
            config = self._limits[limit_type]
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            self._limits[limit_type] = config
            logger.info(f"Updated risk limit: {limit_type}")
            return True
        except Exception as e:
            logger.error(f"Error updating limit: {e}")
            return False

    async def get_limit(self, limit_type: str) -> Optional[RiskLimitConfig]:
        """Get a risk limit"""
        return self._limits.get(limit_type)

    async def get_all_limits(self) -> Dict[str, RiskLimitConfig]:
        """Get all risk limits"""
        return self._limits.copy()

    async def delete_limit(self, limit_type: str) -> bool:
        """Delete a risk limit"""
        if limit_type in self._limits:
            del self._limits[limit_type]
            del self._limit_states[limit_type]
            logger.info(f"Deleted risk limit: {limit_type}")
            return True
        return False

    # =========================================================================
    # Breach Management
    # =========================================================================

    async def get_breaches(
        self,
        symbol: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get risk breaches"""
        breaches = [b.__dict__ for b in self._breaches]
        
        if symbol:
            breaches = [b for b in breaches if b.get('symbol') == symbol]
        
        if resolved is not None:
            breaches = [b for b in breaches if b.get('resolved') == resolved]
        
        breaches.sort(key=lambda x: x.get('timestamp', datetime.min), reverse=True)
        return breaches[:limit]

    async def resolve_breach(
        self,
        breach_id: str,
        resolution: str
    ) -> bool:
        """Resolve a breach"""
        for breach in self._breaches:
            if breach.breach_id == breach_id:
                breach.resolved = True
                breach.resolved_at = datetime.utcnow()
                breach.metadata['resolution'] = resolution
                logger.info(f"Resolved breach: {breach_id}")
                return True
        return False

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start risk monitoring"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Risk monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop risk monitoring"""
        self._is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Risk monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_monitoring:
            try:
                # Monitor each symbol
                for symbol in self._get_monitored_symbols():
                    try:
                        request = RiskMetricsRequest(symbol=symbol)
                        metrics = await self.get_risk_metrics(request)
                        
                        # Check for critical conditions
                        if metrics.risk_level in [RiskLevel.CRITICAL, RiskLevel.EMERGENCY]:
                            await self._handle_critical_risk(metrics)
                        
                    except Exception as e:
                        logger.error(f"Error monitoring {symbol}: {e}")
                
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in risk monitor loop: {e}")
                await asyncio.sleep(10)

    def _get_monitored_symbols(self) -> List[str]:
        """Get symbols being monitored"""
        # Get from config or active market makers
        return self.mm_config.get('symbols', [])

    async def _handle_critical_risk(self, metrics: RiskMetricsResponse) -> None:
        """Handle critical risk"""
        logger.error(f"CRITICAL RISK for {metrics.symbol}: Score {metrics.composite_risk_score}")
        
        # Emergency actions
        await self._emergency_stop(metrics.symbol)
        
        # Notify
        await self._send_emergency_notification(metrics)

    async def _emergency_stop(self, symbol: str) -> None:
        """Emergency stop"""
        logger.error(f"EMERGENCY STOP for {symbol}")
        # Implementation would stop all trading

    async def _send_emergency_notification(
        self,
        metrics: RiskMetricsResponse
    ) -> None:
        """Send emergency notification"""
        message = (
            f"🚨 EMERGENCY RISK ALERT\n"
            f"Symbol: {metrics.symbol}\n"
            f"Risk Score: {metrics.composite_risk_score:.1f}\n"
            f"Risk Level: {metrics.risk_level.value}\n"
            f"Breaches: {len(metrics.breaches)}\n"
            f"Recommendations: {metrics.recommendations[:3]}"
        )
        # Send via all channels

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the risk manager"""
        await self.stop_monitoring()
        self._limits.clear()
        self._limit_states.clear()
        self._breaches.clear()
        logger.info("MarketMakingRiskManager closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/market-making/risk", tags=["Market Making Risk"])


async def get_risk_manager() -> MarketMakingRiskManager:
    """Dependency to get MarketMakingRiskManager instance"""
    return MarketMakingRiskManager()


@router.post("/metrics", response_model=RiskMetricsResponse)
async def get_risk_metrics(
    request: RiskMetricsRequest,
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Get comprehensive risk metrics"""
    return await manager.get_risk_metrics(request)


@router.get("/limits")
async def get_all_limits(
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Get all risk limits"""
    return await manager.get_all_limits()


@router.get("/limits/{limit_type}")
async def get_limit(
    limit_type: str,
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Get a risk limit"""
    limit = await manager.get_limit(limit_type)
    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Limit {limit_type} not found"
        )
    return limit


@router.post("/limits")
async def add_limit(
    config: RiskLimitConfig,
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Add a risk limit"""
    success = await manager.add_limit(config)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add limit"
        )
    return {"success": True}


@router.put("/limits/{limit_type}")
async def update_limit(
    limit_type: str,
    updates: Dict[str, Any] = Body(..., embed=True),
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Update a risk limit"""
    success = await manager.update_limit(limit_type, updates)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Limit {limit_type} not found"
        )
    return {"success": True}


@router.delete("/limits/{limit_type}")
async def delete_limit(
    limit_type: str,
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Delete a risk limit"""
    success = await manager.delete_limit(limit_type)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Limit {limit_type} not found"
        )
    return {"success": True}


@router.get("/breaches")
async def get_breaches(
    symbol: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    limit: int = Query(100, le=1000),
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Get risk breaches"""
    return await manager.get_breaches(symbol, resolved, limit)


@router.post("/breaches/{breach_id}/resolve")
async def resolve_breach(
    breach_id: str,
    resolution: str = Body(..., embed=True),
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Resolve a breach"""
    success = await manager.resolve_breach(breach_id, resolution)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Breach {breach_id} not found"
        )
    return {"success": True}


@router.post("/monitor/start")
async def start_risk_monitoring(
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Start risk monitoring"""
    await manager.start_monitoring()
    return {"status": "started"}


@router.post("/monitor/stop")
async def stop_risk_monitoring(
    manager: MarketMakingRiskManager = Depends(get_risk_manager)
):
    """Stop risk monitoring"""
    await manager.stop_monitoring()
    return {"status": "stopped"}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'MarketMakingRiskManager',
    'RiskLimitType',
    'RiskLevel',
    'RiskAction',
    'RiskLimitConfig',
    'RiskMetricsRequest',
    'RiskMetricsResponse',
    'RiskBreachResponse',
    'RiskContext',
    'RiskLimitState',
    'router'
]
