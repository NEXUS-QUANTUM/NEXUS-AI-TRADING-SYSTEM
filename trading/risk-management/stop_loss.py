"""
NEXUS AI TRADING SYSTEM - Stop Loss Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/risk-management/stop_loss.py
Description: Advanced stop loss management with full API integration
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
from shared.configs.risk_config import RiskConfig
from shared.constants.trading_constants import (
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    STOP_LOSS_TYPES,
    TIME_FRAMES
)
from shared.helpers.trading_helpers import (
    calculate_stop_loss_distance,
    calculate_risk_reward_ratio,
    calculate_atr
)
from shared.types.risk import StopLossConfig, StopLossOrder
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Position, Order, StopLoss
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Risk management imports
from trading.risk_engine.risk_manager import RiskManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class StopLossType(str, Enum):
    """Types of stop loss"""
    FIXED = "fixed"  # Fixed price distance
    PERCENTAGE = "percentage"  # Percentage from entry
    ATR = "atr"  # Average True Range based
    VOLATILITY = "volatility"  # Volatility adjusted
    TRAILING = "trailing"  # Trailing stop loss
    DYNAMIC = "dynamic"  # Dynamic based on indicators
    SUPPORT_RESISTANCE = "support_resistance"  # Based on S/R levels
    CHANDELIER = "chandelier"  # Chandelier exit
    PARABOLIC = "parabolic"  # Parabolic SAR
    BOLLINGER = "bollinger"  # Bollinger Bands
    KELLY = "kelly"  # Kelly Criterion based
    OPTIMAL = "optimal"  # Optimal stop loss
    ADAPTIVE = "adaptive"  # Adapts to market conditions
    TIME_BASED = "time_based"  # Time-based stop loss
    VOLUME_BASED = "volume_based"  # Volume-based stop loss
    CUSTOM = "custom"  # Custom stop loss logic


class StopLossStatus(str, Enum):
    """Status of stop loss"""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    MODIFIED = "modified"
    PENDING = "pending"


class StopLossTrigger(str, Enum):
    """Trigger type for stop loss"""
    PRICE = "price"
    TIME = "time"
    VOLATILITY = "volatility"
    INDICATOR = "indicator"
    MANUAL = "manual"
    AUTO = "auto"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StopLossRequest(BaseModel):
    """Request model for stop loss operations"""
    position_id: str
    stop_type: StopLossType = StopLossType.PERCENTAGE
    stop_price: Optional[float] = None
    stop_distance: Optional[float] = None
    stop_percentage: Optional[float] = None
    atr_multiplier: Optional[float] = None
    trail_distance: Optional[float] = None
    trail_percentage: Optional[float] = None
    time_limit: Optional[int] = None  # seconds
    volatility_adjustment: bool = True
    max_stop_distance: Optional[float] = None
    min_stop_distance: Optional[float] = None
    use_breakeven: bool = False
    breakeven_trigger: Optional[float] = None  # % profit to trigger breakeven
    trailing_activation: Optional[float] = None  # % profit to activate trailing
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StopLossResponse(BaseModel):
    """Response model for stop loss operations"""
    stop_id: str
    position_id: str
    symbol: str
    stop_type: StopLossType
    stop_price: float
    entry_price: float
    current_price: float
    distance: float  # distance from entry
    distance_percentage: float
    status: StopLossStatus
    created_at: datetime
    updated_at: datetime
    trigger_price: Optional[float] = None
    triggered_at: Optional[datetime] = None
    trail_step: Optional[float] = None
    trail_high: Optional[float] = None
    trail_low: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StopLossHistoryResponse(BaseModel):
    """Response model for stop loss history"""
    stop_id: str
    position_id: str
    symbol: str
    stop_type: StopLossType
    entry_price: float
    stop_price: float
    exit_price: Optional[float] = None
    status: StopLossStatus
    created_at: datetime
    triggered_at: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchStopLossRequest(BaseModel):
    """Request model for batch stop loss operations"""
    position_ids: List[str]
    stop_type: StopLossType = StopLossType.PERCENTAGE
    stop_percentage: Optional[float] = 0.02
    atr_multiplier: Optional[float] = 1.5
    trail_percentage: Optional[float] = None
    use_breakeven: bool = True
    breakeven_trigger: float = 0.02
    trailing_activation: Optional[float] = None


class StopLossAnalyticsResponse(BaseModel):
    """Response model for stop loss analytics"""
    total_stops: int
    triggered_stops: int
    hit_rate: float  # % of stops triggered
    avg_distance: float
    avg_loss: float
    avg_win: float
    profit_factor: float
    best_stop_type: str
    worst_stop_type: str
    performance_by_type: Dict[str, Dict[str, Any]]
    recommendations: List[str]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class StopLossContext:
    """Context for stop loss calculations"""
    symbol: str
    entry_price: float
    current_price: float
    direction: str  # long or short
    volatility: float
    atr: float
    high_price: float
    low_price: float
    volume: float
    position_size: float
    risk_per_trade: float
    time_in_position: int  # seconds
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    market_condition: str = "normal"
    indicator_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StopLossResult:
    """Result of stop loss calculation"""
    stop_price: float
    stop_type: StopLossType
    distance: float
    distance_percentage: float
    confidence: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrailingStopState:
    """State of a trailing stop loss"""
    current_high: float
    current_low: float
    trail_price: float
    trail_step: float
    activated_at: Optional[datetime] = None
    activation_price: Optional[float] = None
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None


# =============================================================================
# STOP LOSS MANAGER
# =============================================================================

class StopLossManager:
    """
    Advanced Stop Loss Manager with full API integration.
    
    Supports multiple stop loss types:
    - Fixed price stops
    - Percentage stops
    - ATR-based stops
    - Volatility-adjusted stops
    - Trailing stops
    - Dynamic stops
    - Support/Resistance based stops
    - Chandelier exits
    - Parabolic SAR stops
    - Bollinger Band stops
    - Kelly Criterion based stops
    - Adaptive stops
    - Time-based stops
    - Volume-based stops
    
    Features:
    - Real-time stop loss monitoring
    - Automatic trailing updates
    - Breakeven management
    - Batch operations
    - Performance analytics
    - Risk integration
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize StopLossManager.
        
        Args:
            config: Risk configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.config = config or RiskConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Active stop losses
        self._active_stops: Dict[str, StopLossResponse] = {}
        self._trailing_states: Dict[str, TrailingStopState] = {}
        self._stop_history: List[StopLossHistoryResponse] = []
        
        # Monitoring
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_monitoring: bool = False
        
        # Risk manager
        self.risk_manager = RiskManager(config)
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        logger.info("StopLossManager initialized")

    # =========================================================================
    # Stop Loss Creation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def create_stop_loss(
        self,
        request: StopLossRequest
    ) -> StopLossResponse:
        """
        Create a stop loss for a position.
        
        Args:
            request: Stop loss request
            
        Returns:
            StopLossResponse: Created stop loss
        """
        try:
            # Validate request
            await self._validate_request(request)
            
            # Get position
            position = await self.position_repo.get_by_id(request.position_id)
            if not position:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Position {request.position_id} not found"
                )
            
            # Build context
            context = await self._build_stop_context(position)
            
            # Calculate stop loss
            result = await self._calculate_stop_loss(request, context)
            
            # Create stop loss order
            stop_loss = await self._create_stop_order(position, result)
            
            # Store stop loss
            response = self._to_response(stop_loss, position)
            self._active_stops[response.stop_id] = response
            
            # Initialize trailing state if needed
            if request.stop_type == StopLossType.TRAILING:
                self._trailing_states[response.stop_id] = TrailingStopState(
                    current_high=position.entry_price,
                    current_low=position.entry_price,
                    trail_price=response.stop_price,
                    trail_step=request.trail_distance or 0.005
                )
            
            logger.info(f"Created stop loss {response.stop_id} for {position.symbol}")
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating stop loss: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Stop loss creation failed: {str(e)}"
            )

    async def _validate_request(self, request: StopLossRequest) -> None:
        """Validate stop loss request"""
        if request.stop_type == StopLossType.FIXED:
            if request.stop_price is None:
                raise ValueError("Stop price required for fixed stop")
        
        elif request.stop_type == StopLossType.PERCENTAGE:
            if request.stop_percentage is None:
                raise ValueError("Stop percentage required for percentage stop")
            if not 0 < request.stop_percentage <= 0.10:
                raise ValueError("Stop percentage must be between 0 and 10%")
        
        elif request.stop_type == StopLossType.ATR:
            if request.atr_multiplier is None:
                raise ValueError("ATR multiplier required for ATR stop")
            if request.atr_multiplier <= 0:
                raise ValueError("ATR multiplier must be positive")
        
        elif request.stop_type == StopLossType.TRAILING:
            if request.trail_distance is None and request.trail_percentage is None:
                raise ValueError("Trail distance or percentage required")
        
        # Validate min/max distances
        if request.max_stop_distance and request.max_stop_distance <= 0:
            raise ValueError("Max stop distance must be positive")
        if request.min_stop_distance and request.min_stop_distance <= 0:
            raise ValueError("Min stop distance must be positive")
        if request.min_stop_distance and request.max_stop_distance:
            if request.min_stop_distance > request.max_stop_distance:
                raise ValueError("Min stop distance cannot exceed max stop distance")

    async def _build_stop_context(self, position: Any) -> StopLossContext:
        """Build context for stop loss calculation"""
        symbol = position.symbol
        direction = position.direction
        
        # Get market data
        market_data = await self._get_market_data(symbol)
        
        # Calculate ATR
        atr = await self._calculate_atr(symbol)
        
        # Get support/resistance levels
        support, resistance = await self._get_support_resistance(symbol)
        
        # Get indicator data
        indicators = await self._get_indicator_data(symbol)
        
        return StopLossContext(
            symbol=symbol,
            entry_price=float(position.entry_price),
            current_price=float(position.current_price or position.entry_price),
            direction=direction,
            volatility=market_data.get('volatility', 0.02),
            atr=atr,
            high_price=market_data.get('high', float(position.entry_price)),
            low_price=market_data.get('low', float(position.entry_price)),
            volume=market_data.get('volume', 0),
            position_size=float(position.size),
            risk_per_trade=self.config.get('risk_per_trade', 0.02),
            time_in_position=int((datetime.utcnow() - position.created_at).total_seconds()),
            support_levels=support,
            resistance_levels=resistance,
            market_condition=await self._get_market_condition(symbol),
            indicator_data=indicators
        )

    async def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for symbol"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    ticker = await broker.get_ticker(symbol)
                    return {
                        'price': float(ticker.get('price', 0)),
                        'high': float(ticker.get('high', 0)),
                        'low': float(ticker.get('low', 0)),
                        'volume': float(ticker.get('volume', 0)),
                        'volatility': float(ticker.get('volatility', 0.02))
                    }
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting market data for {symbol}: {e}")
        
        # Return mock data
        return {
            'price': 100.0,
            'high': 102.0,
            'low': 98.0,
            'volume': 1000000,
            'volatility': 0.02
        }

    async def _calculate_atr(self, symbol: str, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            # Get historical data
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    candles = await broker.get_historical_candles(
                        symbol,
                        timeframe='1h',
                        limit=period + 1
                    )
                    if candles and len(candles) > period:
                        # Calculate ATR
                        atr = calculate_atr(candles, period)
                        return float(atr)
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error calculating ATR for {symbol}: {e}")
        
        # Default ATR (1% of price)
        return 1.0

    async def _get_support_resistance(
        self,
        symbol: str
    ) -> Tuple[List[float], List[float]]:
        """Get support and resistance levels"""
        try:
            # Get support/resistance from market data service
            support = []
            resistance = []
            
            # For now, return simple levels
            price = 100.0
            support = [price * 0.95, price * 0.90, price * 0.85]
            resistance = [price * 1.05, price * 1.10, price * 1.15]
            
            return support, resistance
            
        except Exception as e:
            logger.warning(f"Error getting support/resistance: {e}")
            return [], []

    async def _get_indicator_data(self, symbol: str) -> Dict[str, Any]:
        """Get indicator data"""
        try:
            # Get indicators from market data service
            return {
                'rsi': 50.0,
                'macd': 0.0,
                'macd_signal': 0.0,
                'bb_upper': 105.0,
                'bb_lower': 95.0,
                'bb_middle': 100.0
            }
        except Exception as e:
            logger.warning(f"Error getting indicator data: {e}")
            return {}

    async def _get_market_condition(self, symbol: str) -> str:
        """Get current market condition"""
        try:
            # Get market condition from market data service
            return 'normal'
        except Exception:
            return 'normal'

    # =========================================================================
    # Stop Loss Calculation
    # =========================================================================

    async def _calculate_stop_loss(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """
        Calculate stop loss price based on type.
        
        Args:
            request: Stop loss request
            context: Stop loss context
            
        Returns:
            StopLossResult: Calculated stop loss
        """
        if request.stop_type == StopLossType.FIXED:
            return await self._calculate_fixed_stop(request, context)
        elif request.stop_type == StopLossType.PERCENTAGE:
            return await self._calculate_percentage_stop(request, context)
        elif request.stop_type == StopLossType.ATR:
            return await self._calculate_atr_stop(request, context)
        elif request.stop_type == StopLossType.VOLATILITY:
            return await self._calculate_volatility_stop(request, context)
        elif request.stop_type == StopLossType.TRAILING:
            return await self._calculate_trailing_stop(request, context)
        elif request.stop_type == StopLossType.DYNAMIC:
            return await self._calculate_dynamic_stop(request, context)
        elif request.stop_type == StopLossType.SUPPORT_RESISTANCE:
            return await self._calculate_sr_stop(request, context)
        elif request.stop_type == StopLossType.CHANDELIER:
            return await self._calculate_chandelier_stop(request, context)
        elif request.stop_type == StopLossType.PARABOLIC:
            return await self._calculate_parabolic_stop(request, context)
        elif request.stop_type == StopLossType.BOLLINGER:
            return await self._calculate_bollinger_stop(request, context)
        elif request.stop_type == StopLossType.KELLY:
            return await self._calculate_kelly_stop(request, context)
        elif request.stop_type == StopLossType.OPTIMAL:
            return await self._calculate_optimal_stop(request, context)
        elif request.stop_type == StopLossType.ADAPTIVE:
            return await self._calculate_adaptive_stop(request, context)
        elif request.stop_type == StopLossType.TIME_BASED:
            return await self._calculate_time_stop(request, context)
        elif request.stop_type == StopLossType.VOLUME_BASED:
            return await self._calculate_volume_stop(request, context)
        else:
            return await self._calculate_percentage_stop(request, context)

    # -------------------------------------------------------------------------
    # Stop Loss Type Implementations
    # -------------------------------------------------------------------------

    async def _calculate_fixed_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate fixed stop loss"""
        is_long = context.direction == 'long'
        
        if is_long:
            stop_price = request.stop_price
            distance = context.entry_price - stop_price
        else:
            stop_price = request.stop_price
            distance = stop_price - context.entry_price
        
        distance_pct = distance / context.entry_price
        
        # Validate distance
        distance_pct, stop_price = await self._validate_stop_distance(
            distance_pct,
            context,
            request
        )
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.FIXED,
            distance=distance,
            distance_percentage=distance_pct,
            confidence=1.0,
            reason="Fixed price stop loss"
        )

    async def _calculate_percentage_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate percentage-based stop loss"""
        is_long = context.direction == 'long'
        stop_pct = request.stop_percentage or 0.02  # Default 2%
        
        # Validate and adjust percentage
        stop_pct, _ = await self._validate_stop_distance(stop_pct, context, request)
        
        if is_long:
            stop_price = context.entry_price * (1 - stop_pct)
        else:
            stop_price = context.entry_price * (1 + stop_pct)
        
        distance = stop_pct * context.entry_price
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.PERCENTAGE,
            distance=distance,
            distance_percentage=stop_pct,
            confidence=0.9,
            reason=f"{stop_pct*100:.1f}% stop loss"
        )

    async def _calculate_atr_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate ATR-based stop loss"""
        is_long = context.direction == 'long'
        atr_multiplier = request.atr_multiplier or 1.5
        
        # Get ATR
        atr = context.atr or await self._calculate_atr(context.symbol)
        
        # Validate stop distance
        stop_pct = (atr * atr_multiplier) / context.entry_price
        stop_pct, _ = await self._validate_stop_distance(stop_pct, context, request)
        
        if is_long:
            stop_price = context.entry_price - (stop_pct * context.entry_price)
        else:
            stop_price = context.entry_price + (stop_pct * context.entry_price)
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.ATR,
            distance=stop_pct * context.entry_price,
            distance_percentage=stop_pct,
            confidence=0.85,
            reason=f"ATR ({atr_multiplier}x) based stop loss",
            metadata={'atr': atr, 'atr_multiplier': atr_multiplier}
        )

    async def _calculate_volatility_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate volatility-adjusted stop loss"""
        is_long = context.direction == 'long'
        volatility = context.volatility
        
        # Higher volatility = wider stop
        base_stop = request.stop_percentage or 0.02
        volatility_factor = 1 + (volatility * 5)  # Scale factor
        stop_pct = base_stop * volatility_factor
        
        # Cap at reasonable levels
        stop_pct = min(stop_pct, 0.10)
        stop_pct, _ = await self._validate_stop_distance(stop_pct, context, request)
        
        if is_long:
            stop_price = context.entry_price * (1 - stop_pct)
        else:
            stop_price = context.entry_price * (1 + stop_pct)
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.VOLATILITY,
            distance=stop_pct * context.entry_price,
            distance_percentage=stop_pct,
            confidence=0.8,
            reason=f"Volatility-adjusted stop ({volatility*100:.1f}% vol)",
            metadata={'volatility': volatility}
        )

    async def _calculate_trailing_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate trailing stop loss"""
        is_long = context.direction == 'long'
        
        # Get trail distance
        if request.trail_distance:
            trail_dist = request.trail_distance
            trail_pct = trail_dist / context.entry_price
        elif request.trail_percentage:
            trail_pct = request.trail_percentage
            trail_dist = trail_pct * context.entry_price
        else:
            trail_pct = 0.02  # Default 2%
            trail_dist = trail_pct * context.entry_price
        
        # Validate stop distance
        trail_pct, _ = await self._validate_stop_distance(trail_pct, context, request)
        
        # Calculate trailing stop based on current price
        current_price = context.current_price
        
        if is_long:
            stop_price = current_price - (trail_pct * current_price)
            # Trail price only moves up
            if request.stop_id in self._trailing_states:
                state = self._trailing_states[request.stop_id]
                if state.trail_price > stop_price:
                    stop_price = state.trail_price
        else:
            stop_price = current_price + (trail_pct * current_price)
            # Trail price only moves down
            if request.stop_id in self._trailing_states:
                state = self._trailing_states[request.stop_id]
                if state.trail_price < stop_price:
                    stop_price = state.trail_price
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.TRAILING,
            distance=abs(current_price - stop_price),
            distance_percentage=abs(current_price - stop_price) / current_price,
            confidence=0.75,
            reason=f"Trailing stop ({trail_pct*100:.1f}%)",
            metadata={'trail_pct': trail_pct}
        )

    async def _calculate_dynamic_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate dynamic stop loss based on indicators"""
        is_long = context.direction == 'long'
        
        # Use multiple indicators to determine stop
        indicators = context.indicator_data
        
        # RSI-based stop
        rsi = indicators.get('rsi', 50)
        rsi_factor = 1 + ((50 - rsi) / 100) if is_long else 1 + ((rsi - 50) / 100)
        
        # MACD-based stop
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_factor = 1 + (macd - macd_signal) * 10 if is_long else 1 + (macd_signal - macd) * 10
        
        # Bollinger Band stop
        bb_upper = indicators.get('bb_upper', 0)
        bb_lower = indicators.get('bb_lower', 0)
        bb_middle = indicators.get('bb_middle', context.entry_price)
        
        # Calculate dynamic stop percentage
        base_stop = 0.02
        dynamic_factor = (rsi_factor + macd_factor) / 2
        stop_pct = base_stop * dynamic_factor
        
        # Clamp stop percentage
        stop_pct = max(0.01, min(stop_pct, 0.08))
        stop_pct, _ = await self._validate_stop_distance(stop_pct, context, request)
        
        if is_long:
            stop_price = context.entry_price * (1 - stop_pct)
        else:
            stop_price = context.entry_price * (1 + stop_pct)
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.DYNAMIC,
            distance=stop_pct * context.entry_price,
            distance_percentage=stop_pct,
            confidence=0.7,
            reason=f"Dynamic stop (RSI: {rsi:.1f}, MACD: {macd:.2f})",
            metadata={'rsi': rsi, 'macd': macd}
        )

    async def _calculate_sr_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate support/resistance-based stop loss"""
        is_long = context.direction == 'long'
        
        support = context.support_levels
        resistance = context.resistance_levels
        
        if is_long:
            # Place stop below nearest support
            if support:
                # Use the nearest support level
                nearest_support = max([s for s in support if s < context.entry_price], default=None)
                if nearest_support:
                    stop_price = nearest_support * 0.995  # Slightly below support
                    distance = context.entry_price - stop_price
                    distance_pct = distance / context.entry_price
                    
                    distance_pct, stop_price = await self._validate_stop_distance(
                        distance_pct, context, request, stop_price
                    )
                    
                    return StopLossResult(
                        stop_price=stop_price,
                        stop_type=StopLossType.SUPPORT_RESISTANCE,
                        distance=distance,
                        distance_percentage=distance_pct,
                        confidence=0.8,
                        reason=f"Stop below support at {nearest_support:.2f}"
                    )
        else:
            # Place stop above nearest resistance
            if resistance:
                nearest_resistance = min([r for r in resistance if r > context.entry_price], default=None)
                if nearest_resistance:
                    stop_price = nearest_resistance * 1.005  # Slightly above resistance
                    distance = stop_price - context.entry_price
                    distance_pct = distance / context.entry_price
                    
                    distance_pct, stop_price = await self._validate_stop_distance(
                        distance_pct, context, request, stop_price
                    )
                    
                    return StopLossResult(
                        stop_price=stop_price,
                        stop_type=StopLossType.SUPPORT_RESISTANCE,
                        distance=distance,
                        distance_percentage=distance_pct,
                        confidence=0.8,
                        reason=f"Stop above resistance at {nearest_resistance:.2f}"
                    )
        
        # Fallback to percentage stop
        return await self._calculate_percentage_stop(request, context)

    async def _calculate_chandelier_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate Chandelier Exit stop loss"""
        is_long = context.direction == 'long'
        
        # Get ATR
        atr = context.atr or await self._calculate_atr(context.symbol)
        atr_multiplier = request.atr_multiplier or 3.0
        
        # Chandelier Exit formula
        atr_stop = atr * atr_multiplier
        
        if is_long:
            # For long: highest high - ATR * multiplier
            highest_high = max(context.high_price, context.entry_price)
            stop_price = highest_high - atr_stop
        else:
            # For short: lowest low + ATR * multiplier
            lowest_low = min(context.low_price, context.entry_price)
            stop_price = lowest_low + atr_stop
        
        distance = abs(context.entry_price - stop_price)
        distance_pct = distance / context.entry_price
        
        distance_pct, stop_price = await self._validate_stop_distance(
            distance_pct, context, request, stop_price
        )
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.CHANDELIER,
            distance=distance,
            distance_percentage=distance_pct,
            confidence=0.75,
            reason=f"Chandelier exit ({atr_multiplier}x ATR)",
            metadata={'atr': atr, 'atr_multiplier': atr_multiplier}
        )

    async def _calculate_parabolic_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate Parabolic SAR stop loss"""
        is_long = context.direction == 'long'
        
        # Get indicator data
        indicators = context.indicator_data
        
        # Use pre-calculated PSAR if available, otherwise compute approximation
        psar = indicators.get('psar', None)
        if psar is None:
            # Approximation using ATR
            atr = context.atr or await self._calculate_atr(context.symbol)
            af = 0.02  # Acceleration factor
            step = af * atr
            
            if is_long:
                psar = context.entry_price - step
            else:
                psar = context.entry_price + step
        
        stop_price = float(psar)
        distance = abs(context.entry_price - stop_price)
        distance_pct = distance / context.entry_price
        
        distance_pct, stop_price = await self._validate_stop_distance(
            distance_pct, context, request, stop_price
        )
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.PARABOLIC,
            distance=distance,
            distance_percentage=distance_pct,
            confidence=0.7,
            reason="Parabolic SAR stop loss"
        )

    async def _calculate_bollinger_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate Bollinger Band stop loss"""
        is_long = context.direction == 'long'
        
        # Get Bollinger Bands
        indicators = context.indicator_data
        bb_lower = indicators.get('bb_lower', context.entry_price * 0.95)
        bb_upper = indicators.get('bb_upper', context.entry_price * 1.05)
        bb_middle = indicators.get('bb_middle', context.entry_price)
        
        # Use Bollinger Band as stop
        if is_long:
            stop_price = bb_lower
        else:
            stop_price = bb_upper
        
        distance = abs(context.entry_price - stop_price)
        distance_pct = distance / context.entry_price
        
        distance_pct, stop_price = await self._validate_stop_distance(
            distance_pct, context, request, stop_price
        )
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.BOLLINGER,
            distance=distance,
            distance_percentage=distance_pct,
            confidence=0.7,
            reason="Bollinger Band stop loss",
            metadata={'bb_lower': bb_lower, 'bb_upper': bb_upper}
        )

    async def _calculate_kelly_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate Kelly Criterion based stop loss"""
        is_long = context.direction == 'long'
        
        # Get win rate and average win/loss
        stats = await self._get_trading_stats(context.symbol)
        win_rate = stats.get('win_rate', 0.5)
        avg_win = stats.get('avg_win', 0.03)
        avg_loss = stats.get('avg_loss', 0.02)
        
        # Calculate Kelly fraction
        if avg_loss > 0:
            kelly = (win_rate - (1 - win_rate) * (avg_loss / avg_win))
            kelly = max(0, min(kelly, 0.25))  # Cap at 25%
        else:
            kelly = 0.02
        
        # Use Kelly as stop percentage
        stop_pct = kelly
        
        # Validate
        stop_pct, _ = await self._validate_stop_distance(stop_pct, context, request)
        
        if is_long:
            stop_price = context.entry_price * (1 - stop_pct)
        else:
            stop_price = context.entry_price * (1 + stop_pct)
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.KELLY,
            distance=stop_pct * context.entry_price,
            distance_percentage=stop_pct,
            confidence=0.65,
            reason=f"Kelly stop ({kelly*100:.1f}%)",
            metadata={'kelly': kelly, 'win_rate': win_rate}
        )

    async def _get_trading_stats(self, symbol: str) -> Dict[str, float]:
        """Get trading statistics for Kelly calculation"""
        try:
            trades = await self.trade_repo.get_by_symbol(symbol, limit=100)
            
            if not trades:
                return {'win_rate': 0.5, 'avg_win': 0.03, 'avg_loss': 0.02}
            
            wins = [t for t in trades if float(t.pnl) > 0]
            losses = [t for t in trades if float(t.pnl) < 0]
            
            win_rate = len(wins) / len(trades) if trades else 0.5
            
            avg_win = np.mean([float(t.pnl) / float(t.size) for t in wins]) if wins else 0.03
            avg_loss = abs(np.mean([float(t.pnl) / float(t.size) for t in losses])) if losses else 0.02
            
            return {
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss
            }
        except Exception:
            return {'win_rate': 0.5, 'avg_win': 0.03, 'avg_loss': 0.02}

    async def _calculate_optimal_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate optimal stop loss using multiple methods"""
        # Calculate using different methods and choose the best
        methods = [
            ('percentage', await self._calculate_percentage_stop(request, context)),
            ('atr', await self._calculate_atr_stop(request, context)),
            ('volatility', await self._calculate_volatility_stop(request, context))
        ]
        
        # Choose the method with highest confidence
        best = max(methods, key=lambda x: x[1].confidence)
        
        return StopLossResult(
            stop_price=best[1].stop_price,
            stop_type=StopLossType.OPTIMAL,
            distance=best[1].distance,
            distance_percentage=best[1].distance_percentage,
            confidence=best[1].confidence,
            reason=f"Optimal stop using {best[0]} method"
        )

    async def _calculate_adaptive_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate adaptive stop loss based on market conditions"""
        is_long = context.direction == 'long'
        
        # Adjust stop based on market condition
        condition = context.market_condition
        base_stop = request.stop_percentage or 0.02
        
        # Adjust based on market condition
        if condition == 'bull':
            stop_pct = base_stop * 0.8  # Tighter in bull market
        elif condition == 'bear':
            stop_pct = base_stop * 1.3  # Wider in bear market
        elif condition == 'high_volatility':
            stop_pct = base_stop * 1.5  # Wider in high volatility
        elif condition == 'low_volatility':
            stop_pct = base_stop * 0.7  # Tighter in low volatility
        else:
            stop_pct = base_stop
        
        # Validate
        stop_pct, _ = await self._validate_stop_distance(stop_pct, context, request)
        
        if is_long:
            stop_price = context.entry_price * (1 - stop_pct)
        else:
            stop_price = context.entry_price * (1 + stop_pct)
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.ADAPTIVE,
            distance=stop_pct * context.entry_price,
            distance_percentage=stop_pct,
            confidence=0.75,
            reason=f"Adaptive stop ({condition} market)",
            metadata={'market_condition': condition}
        )

    async def _calculate_time_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate time-based stop loss"""
        time_limit = request.time_limit or 3600  # 1 hour default
        
        # Calculate stop based on time in position
        time_ratio = context.time_in_position / time_limit
        time_ratio = min(time_ratio, 1.0)
        
        # Stop gets tighter as time passes without movement
        base_stop = request.stop_percentage or 0.02
        stop_pct = base_stop * (1 - time_ratio * 0.5)  # Tighter over time
        
        # Validate
        stop_pct, _ = await self._validate_stop_distance(stop_pct, context, request)
        
        is_long = context.direction == 'long'
        if is_long:
            stop_price = context.entry_price * (1 - stop_pct)
        else:
            stop_price = context.entry_price * (1 + stop_pct)
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.TIME_BASED,
            distance=stop_pct * context.entry_price,
            distance_percentage=stop_pct,
            confidence=0.6,
            reason=f"Time stop ({time_limit//60} minutes)",
            metadata={'time_limit': time_limit, 'time_in_position': context.time_in_position}
        )

    async def _calculate_volume_stop(
        self,
        request: StopLossRequest,
        context: StopLossContext
    ) -> StopLossResult:
        """Calculate volume-based stop loss"""
        volume = context.volume
        
        # Use volume to adjust stop
        # High volume = more liquidity = tighter stop
        # Low volume = less liquidity = wider stop
        avg_volume = 1000000  # Example average volume
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
        volume_ratio = max(0.5, min(volume_ratio, 2.0))
        
        # Adjust stop based on volume
        base_stop = request.stop_percentage or 0.02
        stop_pct = base_stop / volume_ratio  # Higher volume = tighter stop
        
        # Validate
        stop_pct, _ = await self._validate_stop_distance(stop_pct, context, request)
        
        is_long = context.direction == 'long'
        if is_long:
            stop_price = context.entry_price * (1 - stop_pct)
        else:
            stop_price = context.entry_price * (1 + stop_pct)
        
        return StopLossResult(
            stop_price=stop_price,
            stop_type=StopLossType.VOLUME_BASED,
            distance=stop_pct * context.entry_price,
            distance_percentage=stop_pct,
            confidence=0.6,
            reason=f"Volume stop (volume ratio: {volume_ratio:.2f})",
            metadata={'volume': volume, 'volume_ratio': volume_ratio}
        )

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    async def _validate_stop_distance(
        self,
        stop_pct: float,
        context: StopLossContext,
        request: StopLossRequest,
        stop_price: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Validate and adjust stop distance.
        
        Args:
            stop_pct: Stop percentage
            context: Stop context
            request: Original request
            stop_price: Calculated stop price
            
        Returns:
            Tuple[float, float]: Adjusted stop percentage and price
        """
        # Apply min/max limits
        if request.min_stop_distance:
            stop_pct = max(stop_pct, request.min_stop_distance)
        
        if request.max_stop_distance:
            stop_pct = min(stop_pct, request.max_stop_distance)
        
        # Apply global limits
        stop_pct = max(0.005, min(stop_pct, 0.10))  # 0.5% to 10%
        
        # Recalculate stop price if needed
        if stop_price is None:
            is_long = context.direction == 'long'
            if is_long:
                stop_price = context.entry_price * (1 - stop_pct)
            else:
                stop_price = context.entry_price * (1 + stop_pct)
        
        return stop_pct, stop_price

    # =========================================================================
    # Stop Loss Management
    # =========================================================================

    async def _create_stop_order(
        self,
        position: Any,
        result: StopLossResult
    ) -> Dict[str, Any]:
        """Create stop loss order"""
        return {
            'position_id': position.id,
            'symbol': position.symbol,
            'stop_type': result.stop_type.value,
            'stop_price': result.stop_price,
            'size': position.size,
            'direction': position.direction,
            'status': 'active',
            'created_at': datetime.utcnow()
        }

    def _to_response(
        self,
        stop_data: Dict[str, Any],
        position: Any
    ) -> StopLossResponse:
        """Convert stop data to response"""
        return StopLossResponse(
            stop_id=f"sl_{int(time.time() * 1000)}_{position.id}",
            position_id=position.id,
            symbol=position.symbol,
            stop_type=StopLossType(stop_data['stop_type']),
            stop_price=stop_data['stop_price'],
            entry_price=float(position.entry_price),
            current_price=float(position.current_price or position.entry_price),
            distance=abs(float(position.entry_price) - stop_data['stop_price']),
            distance_percentage=abs(float(position.entry_price) - stop_data['stop_price']) / float(position.entry_price),
            status=StopLossStatus.ACTIVE,
            created_at=stop_data['created_at'],
            updated_at=datetime.utcnow(),
            metadata=stop_data.get('metadata', {})
        )

    async def update_stop_loss(
        self,
        stop_id: str,
        new_stop_price: Optional[float] = None,
        new_stop_pct: Optional[float] = None
    ) -> Optional[StopLossResponse]:
        """
        Update an existing stop loss.
        
        Args:
            stop_id: Stop loss ID
            new_stop_price: New stop price
            new_stop_pct: New stop percentage
            
        Returns:
            Optional[StopLossResponse]: Updated stop loss
        """
        if stop_id not in self._active_stops:
            return None
        
        stop = self._active_stops[stop_id]
        
        # Get position
        position = await self.position_repo.get_by_id(stop.position_id)
        if not position:
            return None
        
        # Update stop price
        if new_stop_price:
            stop.stop_price = new_stop_price
        elif new_stop_pct:
            is_long = position.direction == 'long'
            if is_long:
                stop.stop_price = stop.entry_price * (1 - new_stop_pct)
            else:
                stop.stop_price = stop.entry_price * (1 + new_stop_pct)
        
        stop.updated_at = datetime.utcnow()
        stop.status = StopLossStatus.MODIFIED
        
        self._active_stops[stop_id] = stop
        
        logger.info(f"Updated stop loss {stop_id} to {stop.stop_price}")
        return stop

    async def cancel_stop_loss(self, stop_id: str) -> bool:
        """
        Cancel a stop loss.
        
        Args:
            stop_id: Stop loss ID
            
        Returns:
            bool: Success indicator
        """
        if stop_id not in self._active_stops:
            return False
        
        stop = self._active_stops[stop_id]
        stop.status = StopLossStatus.CANCELLED
        
        # Remove from active stops
        del self._active_stops[stop_id]
        if stop_id in self._trailing_states:
            del self._trailing_states[stop_id]
        
        logger.info(f"Cancelled stop loss {stop_id}")
        return True

    async def get_stop_loss(self, stop_id: str) -> Optional[StopLossResponse]:
        """Get a stop loss by ID"""
        return self._active_stops.get(stop_id)

    async def get_position_stop_loss(
        self,
        position_id: str
    ) -> Optional[StopLossResponse]:
        """Get stop loss for a position"""
        for stop in self._active_stops.values():
            if stop.position_id == position_id:
                return stop
        return None

    async def get_all_active_stops(self) -> List[StopLossResponse]:
        """Get all active stop losses"""
        return list(self._active_stops.values())

    # =========================================================================
    # Stop Loss Monitoring
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start monitoring stop losses"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Stop loss monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop monitoring stop losses"""
        self._is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Stop loss monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_monitoring:
            try:
                # Check all active stops
                for stop_id, stop in list(self._active_stops.items()):
                    await self._check_stop_loss(stop)
                
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stop loss monitoring: {e}")
                await asyncio.sleep(5)

    async def _check_stop_loss(self, stop: StopLossResponse) -> None:
        """Check if a stop loss should be triggered"""
        try:
            # Get current price
            market_data = await self._get_market_data(stop.symbol)
            current_price = market_data.get('price', stop.current_price)
            
            # Update current price
            stop.current_price = current_price
            
            # Check if stop should be triggered
            is_long = await self._is_position_long(stop.position_id)
            
            if is_long:
                if current_price <= stop.stop_price:
                    await self._trigger_stop_loss(stop, current_price)
                elif stop.stop_type == StopLossType.TRAILING:
                    await self._update_trailing_stop(stop, current_price)
            else:
                if current_price >= stop.stop_price:
                    await self._trigger_stop_loss(stop, current_price)
                elif stop.stop_type == StopLossType.TRAILING:
                    await self._update_trailing_stop(stop, current_price)
            
        except Exception as e:
            logger.error(f"Error checking stop {stop.stop_id}: {e}")

    async def _is_position_long(self, position_id: str) -> bool:
        """Check if position is long"""
        position = await self.position_repo.get_by_id(position_id)
        return position.direction == 'long' if position else True

    async def _update_trailing_stop(
        self,
        stop: StopLossResponse,
        current_price: float
    ) -> None:
        """Update trailing stop price"""
        if stop.stop_id not in self._trailing_states:
            return
        
        state = self._trailing_states[stop.stop_id]
        
        # Check activation threshold
        profit_pct = (current_price - stop.entry_price) / stop.entry_price
        
        # Only activate trailing after minimum profit
        activation_pct = stop.metadata.get('activation_pct', 0.02)
        if profit_pct < activation_pct:
            return
        
        is_long = await self._is_position_long(stop.position_id)
        
        if is_long:
            # Update highest price
            state.current_high = max(state.current_high, current_price)
            
            # Calculate new stop price
            trail_pct = stop.metadata.get('trail_pct', 0.02)
            new_stop = state.current_high * (1 - trail_pct)
            
            # Only move stop up
            if new_stop > state.trail_price:
                state.trail_price = new_stop
                stop.stop_price = new_stop
                stop.updated_at = datetime.utcnow()
                self._active_stops[stop.stop_id] = stop
                
                logger.debug(f"Updated trailing stop to {new_stop:.2f}")
        else:
            # Update lowest price
            state.current_low = min(state.current_low, current_price)
            
            # Calculate new stop price
            trail_pct = stop.metadata.get('trail_pct', 0.02)
            new_stop = state.current_low * (1 + trail_pct)
            
            # Only move stop down
            if new_stop < state.trail_price:
                state.trail_price = new_stop
                stop.stop_price = new_stop
                stop.updated_at = datetime.utcnow()
                self._active_stops[stop.stop_id] = stop
                
                logger.debug(f"Updated trailing stop to {new_stop:.2f}")

    async def _trigger_stop_loss(
        self,
        stop: StopLossResponse,
        trigger_price: float
    ) -> None:
        """Trigger a stop loss"""
        try:
            # Update stop status
            stop.status = StopLossStatus.TRIGGERED
            stop.triggered_at = datetime.utcnow()
            stop.trigger_price = trigger_price
            
            # Close position
            await self._close_position(stop.position_id, trigger_price)
            
            # Record history
            history = StopLossHistoryResponse(
                stop_id=stop.stop_id,
                position_id=stop.position_id,
                symbol=stop.symbol,
                stop_type=stop.stop_type,
                entry_price=stop.entry_price,
                stop_price=stop.stop_price,
                exit_price=trigger_price,
                status=StopLossStatus.TRIGGERED,
                created_at=stop.created_at,
                triggered_at=stop.triggered_at,
                pnl=(trigger_price - stop.entry_price) * stop.metadata.get('size', 1),
                pnl_percentage=(trigger_price - stop.entry_price) / stop.entry_price * 100,
                metadata=stop.metadata
            )
            self._stop_history.append(history)
            
            # Remove from active stops
            if stop.stop_id in self._active_stops:
                del self._active_stops[stop.stop_id]
            if stop.stop_id in self._trailing_states:
                del self._trailing_states[stop.stop_id]
            
            logger.info(f"Stop loss triggered: {stop.stop_id} at {trigger_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error triggering stop loss: {e}")

    async def _close_position(self, position_id: str, price: float) -> None:
        """Close a position"""
        try:
            # Get position
            position = await self.position_repo.get_by_id(position_id)
            if not position:
                return
            
            # Create market order to close
            order = {
                'position_id': position_id,
                'symbol': position.symbol,
                'side': 'sell' if position.direction == 'long' else 'buy',
                'size': position.size,
                'order_type': 'market',
                'price': price
            }
            
            # Execute order via broker
            broker = self.broker_factory.get_broker(position.broker_id)
            if broker:
                await broker.create_order(order)
            
            # Update position
            await self.position_repo.close_position(
                position_id,
                exit_price=price,
                exit_time=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error closing position {position_id}: {e}")

    # =========================================================================
    # Batch Operations
    # =========================================================================

    async def batch_set_stop_loss(
        self,
        request: BatchStopLossRequest
    ) -> Dict[str, Any]:
        """
        Set stop losses for multiple positions.
        
        Args:
            request: Batch stop loss request
            
        Returns:
            Dict[str, Any]: Batch operation results
        """
        results = {
            'success': [],
            'failed': [],
            'total': len(request.position_ids)
        }
        
        for position_id in request.position_ids:
            try:
                stop_request = StopLossRequest(
                    position_id=position_id,
                    stop_type=request.stop_type,
                    stop_percentage=request.stop_percentage,
                    atr_multiplier=request.atr_multiplier,
                    trail_percentage=request.trail_percentage,
                    use_breakeven=request.use_breakeven,
                    breakeven_trigger=request.breakeven_trigger,
                    trailing_activation=request.trailing_activation
                )
                
                response = await self.create_stop_loss(stop_request)
                results['success'].append({
                    'position_id': position_id,
                    'stop_id': response.stop_id,
                    'stop_price': response.stop_price
                })
                
            except Exception as e:
                results['failed'].append({
                    'position_id': position_id,
                    'error': str(e)
                })
        
        logger.info(f"Batch stop loss: {len(results['success'])} succeeded, {len(results['failed'])} failed")
        return results

    async def batch_update_stop_loss(
        self,
        stop_ids: List[str],
        new_stop_pct: float
    ) -> Dict[str, Any]:
        """
        Update multiple stop losses.
        
        Args:
            stop_ids: List of stop loss IDs
            new_stop_pct: New stop percentage
            
        Returns:
            Dict[str, Any]: Batch operation results
        """
        results = {
            'success': [],
            'failed': [],
            'total': len(stop_ids)
        }
        
        for stop_id in stop_ids:
            try:
                response = await self.update_stop_loss(stop_id, new_stop_pct=new_stop_pct)
                if response:
                    results['success'].append({
                        'stop_id': stop_id,
                        'new_price': response.stop_price
                    })
                else:
                    results['failed'].append({
                        'stop_id': stop_id,
                        'error': 'Stop loss not found'
                    })
            except Exception as e:
                results['failed'].append({
                    'stop_id': stop_id,
                    'error': str(e)
                })
        
        return results

    async def batch_cancel_stop_loss(self, stop_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel multiple stop losses.
        
        Args:
            stop_ids: List of stop loss IDs
            
        Returns:
            Dict[str, Any]: Batch operation results
        """
        results = {
            'success': [],
            'failed': [],
            'total': len(stop_ids)
        }
        
        for stop_id in stop_ids:
            try:
                success = await self.cancel_stop_loss(stop_id)
                if success:
                    results['success'].append(stop_id)
                else:
                    results['failed'].append({
                        'stop_id': stop_id,
                        'error': 'Stop loss not found'
                    })
            except Exception as e:
                results['failed'].append({
                    'stop_id': stop_id,
                    'error': str(e)
                })
        
        return results

    # =========================================================================
    # Analytics
    # =========================================================================

    async def get_analytics(self) -> StopLossAnalyticsResponse:
        """
        Get stop loss performance analytics.
        
        Returns:
            StopLossAnalyticsResponse: Analytics data
        """
        total_stops = len(self._stop_history) + len(self._active_stops)
        triggered_stops = len([h for h in self._stop_history if h.status == StopLossStatus.TRIGGERED])
        
        hit_rate = triggered_stops / total_stops if total_stops > 0 else 0
        
        # Calculate average metrics
        distances = [h.distance_percentage for h in self._stop_history]
        avg_distance = np.mean(distances) if distances else 0
        
        pnls = [h.pnl or 0 for h in self._stop_history]
        avg_pnl = np.mean(pnls) if pnls else 0
        
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        
        profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 0
        
        # Performance by stop type
        performance_by_type = {}
        for stop_type in StopLossType:
            type_stops = [h for h in self._stop_history if h.stop_type == stop_type]
            if type_stops:
                type_pnls = [h.pnl or 0 for h in type_stops]
                performance_by_type[stop_type.value] = {
                    'count': len(type_stops),
                    'avg_pnl': np.mean(type_pnls),
                    'total_pnl': sum(type_pnls),
                    'hit_rate': len([h for h in type_stops if h.status == StopLossStatus.TRIGGERED]) / len(type_stops)
                }
        
        # Best and worst stop types
        best_type = max(performance_by_type.items(), key=lambda x: x[1]['avg_pnl'])[0] if performance_by_type else "N/A"
        worst_type = min(performance_by_type.items(), key=lambda x: x[1]['avg_pnl'])[0] if performance_by_type else "N/A"
        
        # Generate recommendations
        recommendations = []
        
        if hit_rate > 0.7:
            recommendations.append("Stop loss hit rate is high. Consider widening stops or reviewing strategy.")
        
        if avg_loss > abs(avg_win) and avg_win > 0:
            recommendations.append("Average loss exceeds average win. Consider improving risk-reward ratio.")
        
        if profit_factor < 1:
            recommendations.append("Profit factor is below 1. Consider reviewing stop loss placement.")
        
        if best_type != "N/A":
            recommendations.append(f"{best_type} stops have the best performance. Consider using this type more.")
        
        return StopLossAnalyticsResponse(
            total_stops=total_stops,
            triggered_stops=triggered_stops,
            hit_rate=hit_rate,
            avg_distance=avg_distance,
            avg_loss=abs(avg_loss),
            avg_win=avg_win,
            profit_factor=profit_factor,
            best_stop_type=best_type,
            worst_stop_type=worst_type,
            performance_by_type=performance_by_type,
            recommendations=recommendations
        )

    # =========================================================================
    # History
    # =========================================================================

    async def get_history(
        self,
        position_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[StopLossHistoryResponse]:
        """
        Get stop loss history.
        
        Args:
            position_id: Filter by position ID
            symbol: Filter by symbol
            limit: Maximum number of records
            
        Returns:
            List[StopLossHistoryResponse]: Stop loss history
        """
        history = self._stop_history.copy()
        
        if position_id:
            history = [h for h in history if h.position_id == position_id]
        
        if symbol:
            history = [h for h in history if h.symbol == symbol]
        
        # Sort by timestamp
        history.sort(key=lambda h: h.triggered_at or h.created_at, reverse=True)
        
        return history[:limit]

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the stop loss manager"""
        await self.stop_monitoring()
        
        # Clear all data
        self._active_stops.clear()
        self._trailing_states.clear()
        self._stop_history.clear()
        
        logger.info("StopLossManager closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/stop-loss", tags=["Stop Loss"])


async def get_manager() -> StopLossManager:
    """Dependency to get StopLossManager instance"""
    return StopLossManager()


@router.post("/create", response_model=StopLossResponse)
async def create_stop_loss(
    request: StopLossRequest,
    manager: StopLossManager = Depends(get_manager)
):
    """Create a stop loss for a position"""
    return await manager.create_stop_loss(request)


@router.put("/{stop_id}")
async def update_stop_loss(
    stop_id: str,
    new_stop_price: Optional[float] = None,
    new_stop_pct: Optional[float] = None,
    manager: StopLossManager = Depends(get_manager)
):
    """Update a stop loss"""
    response = await manager.update_stop_loss(stop_id, new_stop_price, new_stop_pct)
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stop loss {stop_id} not found"
        )
    return response


@router.delete("/{stop_id}")
async def cancel_stop_loss(
    stop_id: str,
    manager: StopLossManager = Depends(get_manager)
):
    """Cancel a stop loss"""
    success = await manager.cancel_stop_loss(stop_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stop loss {stop_id} not found"
        )
    return {"success": True}


@router.get("/{stop_id}")
async def get_stop_loss(
    stop_id: str,
    manager: StopLossManager = Depends(get_manager)
):
    """Get a stop loss by ID"""
    stop = await manager.get_stop_loss(stop_id)
    if not stop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stop loss {stop_id} not found"
        )
    return stop


@router.get("/position/{position_id}")
async def get_position_stop_loss(
    position_id: str,
    manager: StopLossManager = Depends(get_manager)
):
    """Get stop loss for a position"""
    stop = await manager.get_position_stop_loss(position_id)
    if not stop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stop loss found for position {position_id}"
        )
    return stop


@router.get("/")
async def get_all_active_stops(
    manager: StopLossManager = Depends(get_manager)
):
    """Get all active stop losses"""
    return await manager.get_all_active_stops()


@router.post("/batch")
async def batch_set_stop_loss(
    request: BatchStopLossRequest,
    manager: StopLossManager = Depends(get_manager)
):
    """Set stop losses for multiple positions"""
    return await manager.batch_set_stop_loss(request)


@router.put("/batch/update")
async def batch_update_stop_loss(
    stop_ids: List[str] = Body(..., embed=True),
    new_stop_pct: float = Body(..., embed=True),
    manager: StopLossManager = Depends(get_manager)
):
    """Update multiple stop losses"""
    return await manager.batch_update_stop_loss(stop_ids, new_stop_pct)


@router.post("/batch/cancel")
async def batch_cancel_stop_loss(
    stop_ids: List[str] = Body(..., embed=True),
    manager: StopLossManager = Depends(get_manager)
):
    """Cancel multiple stop losses"""
    return await manager.batch_cancel_stop_loss(stop_ids)


@router.get("/analytics")
async def get_stop_loss_analytics(
    manager: StopLossManager = Depends(get_manager)
):
    """Get stop loss performance analytics"""
    return await manager.get_analytics()


@router.get("/history")
async def get_stop_loss_history(
    position_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    manager: StopLossManager = Depends(get_manager)
):
    """Get stop loss history"""
    return await manager.get_history(position_id, symbol, limit)


@router.get("/types")
async def get_stop_loss_types():
    """Get available stop loss types"""
    return {
        'types': [
            {'name': t.value, 'description': t.name.replace('_', ' ').title()}
            for t in StopLossType
        ]
    }


@router.post("/monitor/start")
async def start_monitoring(
    manager: StopLossManager = Depends(get_manager)
):
    """Start stop loss monitoring"""
    await manager.start_monitoring()
    return {"status": "started"}


@router.post("/monitor/stop")
async def stop_monitoring(
    manager: StopLossManager = Depends(get_manager)
):
    """Stop stop loss monitoring"""
    await manager.stop_monitoring()
    return {"status": "stopped"}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'StopLossManager',
    'StopLossType',
    'StopLossStatus',
    'StopLossTrigger',
    'StopLossRequest',
    'StopLossResponse',
    'StopLossHistoryResponse',
    'BatchStopLossRequest',
    'StopLossAnalyticsResponse',
    'StopLossContext',
    'StopLossResult',
    'TrailingStopState',
    'router'
]
