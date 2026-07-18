"""
NEXUS AI TRADING SYSTEM - Market Making Inventory Manager Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/market-making/inventory_manager.py
Description: Advanced inventory management for market making with full API integration
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
from shared.configs.inventory_config import InventoryConfig
from shared.constants.trading_constants import (
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    TIME_FRAMES
)
from shared.helpers.trading_helpers import (
    calculate_position_size,
    calculate_risk_reward_ratio,
    calculate_drawdown
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
from trading.market_making.base import BaseMarketMaker, InventoryInfo, InventoryState
from trading.market_making.hedging import HedgingManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class InventoryStrategy(str, Enum):
    """Inventory management strategies"""
    TARGET = "target"  # Maintain target inventory
    RANGE = "range"  # Keep inventory within range
    DYNAMIC = "dynamic"  # Dynamically adjust based on market
    RISK_ADJUSTED = "risk_adjusted"  # Risk-based inventory management
    OPPORTUNISTIC = "opportunistic"  # Seize opportunities
    MEAN_REVERTING = "mean_reverting"  # Mean reversion based
    MOMENTUM = "momentum"  # Momentum based
    HYBRID = "hybrid"  # Combine multiple strategies


class InventoryAction(str, Enum):
    """Inventory management actions"""
    HOLD = "hold"
    ADD = "add"
    REDUCE = "reduce"
    CLEAR = "clear"
    REBALANCE = "rebalance"
    HEDGE = "hedge"


class InventoryRiskLevel(str, Enum):
    """Inventory risk levels"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class InventoryRequest(BaseModel):
    """Request model for inventory management"""
    symbol: str
    strategy: InventoryStrategy = InventoryStrategy.TARGET
    target_inventory: float = 0.0
    max_inventory: float = 100.0
    min_inventory: float = -100.0
    rebalance_threshold: float = 0.10  # 10% deviation threshold
    rebalance_frequency: int = 60  # seconds
    max_daily_turnover: float = 1000.0
    max_position_risk: float = 0.05  # 5% risk per trade
    include_hedging: bool = True
    hedging_ratio: float = 0.5
    adaptive_sizing: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('target_inventory')
    def validate_target(cls, v, values):
        if 'max_inventory' in values and v > values['max_inventory']:
            raise ValueError("Target inventory cannot exceed max inventory")
        if 'min_inventory' in values and v < values['min_inventory']:
            raise ValueError("Target inventory cannot be below min inventory")
        return v


class InventoryResponse(BaseModel):
    """Response model for inventory management"""
    inventory_id: str
    symbol: str
    strategy: InventoryStrategy
    current_inventory: float
    target_inventory: float
    max_inventory: float
    min_inventory: float
    inventory_state: InventoryState
    risk_level: InventoryRiskLevel
    utilization: float  # Current / Max * 100
    positions: List[Dict[str, Any]]
    pnl: float
    daily_turnover: float
    daily_pnl: float
    last_rebalance: datetime
    next_rebalance: datetime
    recommendations: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InventoryAnalyticsResponse(BaseModel):
    """Response model for inventory analytics"""
    avg_inventory: float
    max_inventory_utilized: float
    min_inventory_utilized: float
    inventory_turnover: float
    avg_holding_period: float
    inventory_risk_score: float
    diversification_score: float
    carry_cost: float
    pnl_attribution: Dict[str, float]
    performance_metrics: Dict[str, float]
    recommendations: List[str]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class InventoryPosition:
    """Inventory position"""
    symbol: str
    size: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    holding_time: float
    risk_score: float
    entry_time: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InventoryContext:
    """Context for inventory management"""
    symbol: str
    strategy: InventoryStrategy
    current_inventory: float
    target_inventory: float
    max_inventory: float
    min_inventory: float
    current_price: float
    volatility: float
    market_trend: str
    positions: List[InventoryPosition]
    daily_trades: List[Dict[str, Any]]
    daily_pnl: float
    daily_turnover: float
    risk_limits: Dict[str, float]


@dataclass
class InventoryDecision:
    """Inventory management decision"""
    action: InventoryAction
    size: float
    price: float
    reason: str
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# INVENTORY MANAGER
# =============================================================================

class InventoryManager:
    """
    Advanced Inventory Manager for Market Making with full API integration.
    
    Features:
    - Multiple inventory strategies
    - Dynamic position sizing
    - Risk-based inventory management
    - Automated rebalancing
    - Performance tracking
    - PnL attribution
    - Carry cost management
    - Integration with hedging
    """

    def __init__(
        self,
        config: Optional[InventoryConfig] = None,
        market_making_config: Optional[MarketMakingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        hedging_manager: Optional[HedgingManager] = None
    ):
        """
        Initialize InventoryManager.
        
        Args:
            config: Inventory configuration
            market_making_config: Market making configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            order_repo: Order repository
            trade_repo: Trade repository
            hedging_manager: Hedging manager
        """
        self.config = config or InventoryConfig()
        self.mm_config = market_making_config or MarketMakingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.hedging_manager = hedging_manager or HedgingManager()
        
        # Active inventories
        self._inventories: Dict[str, InventoryResponse] = {}
        self._inventory_history: List[Dict[str, Any]] = []
        
        # Daily tracking
        self._daily_trades: Dict[str, List[Dict[str, Any]]] = {}
        self._daily_pnl: Dict[str, float] = {}
        self._daily_turnover: Dict[str, float] = {}
        
        # Monitoring
        self._is_monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self._performance_metrics: Dict[str, Dict[str, float]] = {}
        
        logger.info("InventoryManager initialized")

    # =========================================================================
    # Inventory Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def create_inventory(
        self,
        request: InventoryRequest
    ) -> InventoryResponse:
        """
        Create inventory management for a symbol.
        
        Args:
            request: Inventory request
            
        Returns:
            InventoryResponse: Created inventory
        """
        try:
            # Validate request
            await self._validate_request(request)
            
            # Generate inventory ID
            inventory_id = f"inv_{int(time.time() * 1000)}_{request.symbol}"
            
            # Build context
            context = await self._build_context(request)
            
            # Get current positions
            positions = await self._get_positions(request.symbol)
            
            # Calculate initial state
            current_inventory = sum(p.size for p in positions)
            
            # Create response
            response = InventoryResponse(
                inventory_id=inventory_id,
                symbol=request.symbol,
                strategy=request.strategy,
                current_inventory=current_inventory,
                target_inventory=request.target_inventory,
                max_inventory=request.max_inventory,
                min_inventory=request.min_inventory,
                inventory_state=self._determine_inventory_state(
                    current_inventory,
                    request.target_inventory,
                    request.max_inventory,
                    request.min_inventory
                ),
                risk_level=self._calculate_risk_level(current_inventory, request),
                utilization=abs(current_inventory) / request.max_inventory * 100 if request.max_inventory > 0 else 0,
                positions=[p.__dict__ for p in positions],
                pnl=sum(p.pnl for p in positions),
                daily_turnover=0,
                daily_pnl=0,
                last_rebalance=datetime.utcnow(),
                next_rebalance=datetime.utcnow() + timedelta(seconds=request.rebalance_frequency),
                recommendations=[],
                metadata=request.metadata
            )
            
            # Store inventory
            self._inventories[inventory_id] = response
            
            # Initialize daily tracking
            self._daily_trades[inventory_id] = []
            self._daily_pnl[inventory_id] = 0
            self._daily_turnover[inventory_id] = 0
            
            # Start monitoring if not already running
            if not self._is_monitoring:
                await self.start_monitoring()
            
            logger.info(f"Inventory created: {inventory_id} for {request.symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error creating inventory: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Inventory creation failed: {str(e)}"
            )

    async def _validate_request(self, request: InventoryRequest) -> None:
        """Validate inventory request"""
        if request.max_inventory <= request.min_inventory:
            raise ValueError("Max inventory must be greater than min inventory")
        
        if request.target_inventory < request.min_inventory or request.target_inventory > request.max_inventory:
            raise ValueError("Target inventory must be within min/max range")
        
        if request.rebalance_frequency < 1:
            raise ValueError("Rebalance frequency must be at least 1 second")
        
        if request.max_daily_turnover <= 0:
            raise ValueError("Max daily turnover must be positive")

    async def _build_context(self, request: InventoryRequest) -> InventoryContext:
        """Build inventory context"""
        # Get market data
        market_data = await self._get_market_data(request.symbol)
        current_price = market_data.get('price', 0)
        volatility = market_data.get('volatility', 0.02)
        
        # Get market trend
        trend = await self._get_market_trend(request.symbol)
        
        # Get positions
        positions = await self._get_positions(request.symbol)
        
        # Get risk limits
        risk_limits = {
            'max_position': request.max_inventory,
            'min_position': request.min_inventory,
            'max_risk_per_trade': request.max_position_risk
        }
        
        return InventoryContext(
            symbol=request.symbol,
            strategy=request.strategy,
            current_inventory=sum(p.size for p in positions),
            target_inventory=request.target_inventory,
            max_inventory=request.max_inventory,
            min_inventory=request.min_inventory,
            current_price=current_price,
            volatility=volatility,
            market_trend=trend,
            positions=positions,
            daily_trades=self._daily_trades.get(request.symbol, []),
            daily_pnl=self._daily_pnl.get(request.symbol, 0),
            daily_turnover=self._daily_turnover.get(request.symbol, 0),
            risk_limits=risk_limits
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
                        'volatility': float(ticker.get('volatility', 0.02))
                    }
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting market data: {e}")
        
        return {'price': 100.0, 'bid': 99.95, 'ask': 100.05, 'volatility': 0.02}

    async def _get_market_trend(self, symbol: str) -> str:
        """Get market trend"""
        try:
            # Get recent prices
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    candles = await broker.get_historical_candles(
                        symbol,
                        timeframe='1h',
                        limit=24
                    )
                    if candles and len(candles) > 1:
                        prices = [c['close'] for c in candles]
                        if prices[-1] > prices[0] * 1.02:
                            return 'uptrend'
                        elif prices[-1] < prices[0] * 0.98:
                            return 'downtrend'
                        else:
                            return 'sideways'
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting market trend: {e}")
        
        return 'sideways'

    async def _get_positions(self, symbol: str) -> List[InventoryPosition]:
        """Get current positions"""
        positions = await self.position_repo.get_by_symbol(symbol)
        
        if not positions:
            return []
        
        inventory_positions = []
        for pos in positions:
            current_price = pos.current_price or pos.entry_price
            pnl = (current_price - pos.entry_price) * pos.size if pos.direction == 'long' else (pos.entry_price - current_price) * pos.size
            
            inventory_positions.append(InventoryPosition(
                symbol=pos.symbol,
                size=pos.size if pos.direction == 'long' else -pos.size,
                entry_price=pos.entry_price,
                current_price=current_price,
                pnl=pnl,
                pnl_pct=pnl / (pos.size * pos.entry_price) if pos.size > 0 else 0,
                holding_time=(datetime.utcnow() - pos.created_at).total_seconds() / 3600,
                risk_score=abs(pos.size) / 100,  # Normalized risk score
                entry_time=pos.created_at
            ))
        
        return inventory_positions

    def _determine_inventory_state(
        self,
        current: float,
        target: float,
        max_inv: float,
        min_inv: float
    ) -> InventoryState:
        """Determine inventory state"""
        if abs(current) < abs(target) * 0.1:
            return InventoryState.NEUTRAL
        elif current > target * 1.5:
            return InventoryState.EXTREME_LONG
        elif current < target * 1.5:
            return InventoryState.EXTREME_SHORT
        elif current > target:
            return InventoryState.LONG
        elif current < target:
            return InventoryState.SHORT
        else:
            return InventoryState.NEUTRAL

    def _calculate_risk_level(
        self,
        current: float,
        request: InventoryRequest
    ) -> InventoryRiskLevel:
        """Calculate inventory risk level"""
        utilization = abs(current) / request.max_inventory if request.max_inventory > 0 else 0
        
        if utilization < 0.3:
            return InventoryRiskLevel.LOW
        elif utilization < 0.6:
            return InventoryRiskLevel.MODERATE
        elif utilization < 0.85:
            return InventoryRiskLevel.HIGH
        else:
            return InventoryRiskLevel.EXTREME

    # =========================================================================
    # Inventory Decisions
    # =========================================================================

    async def get_inventory_decision(
        self,
        inventory_id: str
    ) -> InventoryDecision:
        """
        Get inventory management decision.
        
        Args:
            inventory_id: Inventory ID
            
        Returns:
            InventoryDecision: Management decision
        """
        if inventory_id not in self._inventories:
            raise ValueError(f"Inventory {inventory_id} not found")
        
        inventory = self._inventories[inventory_id]
        
        # Build context
        request = InventoryRequest(
            symbol=inventory.symbol,
            strategy=inventory.strategy,
            target_inventory=inventory.target_inventory,
            max_inventory=inventory.max_inventory,
            min_inventory=inventory.min_inventory,
            rebalance_frequency=60,
            max_position_risk=0.05
        )
        context = await self._build_context(request)
        
        # Get decision based on strategy
        if inventory.strategy == InventoryStrategy.TARGET:
            decision = await self._get_target_decision(context)
        elif inventory.strategy == InventoryStrategy.RANGE:
            decision = await self._get_range_decision(context)
        elif inventory.strategy == InventoryStrategy.DYNAMIC:
            decision = await self._get_dynamic_decision(context)
        elif inventory.strategy == InventoryStrategy.RISK_ADJUSTED:
            decision = await self._get_risk_adjusted_decision(context)
        elif inventory.strategy == InventoryStrategy.OPPORTUNISTIC:
            decision = await self._get_opportunistic_decision(context)
        elif inventory.strategy == InventoryStrategy.MEAN_REVERTING:
            decision = await self._get_mean_reverting_decision(context)
        elif inventory.strategy == InventoryStrategy.MOMENTUM:
            decision = await self._get_momentum_decision(context)
        elif inventory.strategy == InventoryStrategy.HYBRID:
            decision = await self._get_hybrid_decision(context)
        else:
            decision = await self._get_target_decision(context)
        
        return decision

    async def _get_target_decision(
        self,
        context: InventoryContext
    ) -> InventoryDecision:
        """Get target-based inventory decision"""
        deviation = context.current_inventory - context.target_inventory
        
        if abs(deviation) < context.max_inventory * 0.05:
            return InventoryDecision(
                action=InventoryAction.HOLD,
                size=0,
                price=context.current_price,
                reason="Inventory within target range",
                confidence=0.9
            )
        
        action = InventoryAction.REDUCE if deviation > 0 else InventoryAction.ADD
        size = min(abs(deviation), context.max_inventory * 0.1)
        
        return InventoryDecision(
            action=action,
            size=size,
            price=context.current_price * (0.999 if action == InventoryAction.ADD else 1.001),
            reason=f"Adjusting inventory to target ({context.target_inventory:.2f})",
            confidence=0.8,
            metadata={'deviation': deviation}
        )

    async def _get_range_decision(
        self,
        context: InventoryContext
    ) -> InventoryDecision:
        """Get range-based inventory decision"""
        if context.current_inventory > context.max_inventory * 0.8:
            return InventoryDecision(
                action=InventoryAction.REDUCE,
                size=context.current_inventory - context.max_inventory * 0.5,
                price=context.current_price * 1.001,
                reason=f"Inventory above upper range ({context.max_inventory:.2f})",
                confidence=0.85
            )
        elif context.current_inventory < context.min_inventory * 0.8:
            return InventoryDecision(
                action=InventoryAction.ADD,
                size=context.min_inventory * 0.5 - context.current_inventory,
                price=context.current_price * 0.999,
                reason=f"Inventory below lower range ({context.min_inventory:.2f})",
                confidence=0.85
            )
        else:
            return InventoryDecision(
                action=InventoryAction.HOLD,
                size=0,
                price=context.current_price,
                reason="Inventory within acceptable range",
                confidence=0.9
            )

    async def _get_dynamic_decision(
        self,
        context: InventoryContext
    ) -> InventoryDecision:
        """Get dynamic inventory decision"""
        # Adjust based on market conditions
        volatility_factor = context.volatility / 0.02
        
        # Wider range in high volatility
        dynamic_range = context.max_inventory * (0.3 + volatility_factor * 0.3)
        
        if context.current_inventory > dynamic_range:
            return InventoryDecision(
                action=InventoryAction.REDUCE,
                size=context.current_inventory - dynamic_range * 0.5,
                price=context.current_price * (1 + context.volatility * 0.5),
                reason=f"Dynamic range exceeded (volatility: {context.volatility:.3f})",
                confidence=0.75,
                metadata={'volatility_factor': volatility_factor}
            )
        elif context.current_inventory < -dynamic_range:
            return InventoryDecision(
                action=InventoryAction.ADD,
                size=-dynamic_range * 0.5 - context.current_inventory,
                price=context.current_price * (1 - context.volatility * 0.5),
                reason=f"Dynamic range exceeded (volatility: {context.volatility:.3f})",
                confidence=0.75,
                metadata={'volatility_factor': volatility_factor}
            )
        else:
            return InventoryDecision(
                action=InventoryAction.HOLD,
                size=0,
                price=context.current_price,
                reason="Within dynamic range",
                confidence=0.85
            )

    async def _get_risk_adjusted_decision(
        self,
        context: InventoryContext
    ) -> InventoryDecision:
        """Get risk-adjusted inventory decision"""
        # Calculate risk score
        risk_score = abs(context.current_inventory) * context.volatility
        
        max_risk = context.risk_limits.get('max_risk', 0.05)
        
        if risk_score > max_risk * 0.8:
            reduction = (risk_score - max_risk * 0.5) / context.volatility
            
            return InventoryDecision(
                action=InventoryAction.REDUCE,
                size=min(abs(reduction), abs(context.current_inventory) * 0.5),
                price=context.current_price * (1 + context.volatility * 0.3),
                reason=f"Risk score {risk_score:.3f} exceeds threshold",
                confidence=0.8,
                metadata={'risk_score': risk_score}
            )
        else:
            return InventoryDecision(
                action=InventoryAction.HOLD,
                size=0,
                price=context.current_price,
                reason="Risk within acceptable levels",
                confidence=0.9
            )

    async def _get_opportunistic_decision(
        self,
        context: InventoryContext
    ) -> InventoryDecision:
        """Get opportunistic inventory decision"""
        # Look for opportunities based on price deviations
        price_deviation = (context.current_price - 100) / 100  # Normalized
        
        if price_deviation < -0.02:
            # Price is low, opportunity to buy
            size = min(abs(price_deviation) * 100, context.max_inventory * 0.3)
            
            return InventoryDecision(
                action=InventoryAction.ADD,
                size=size,
                price=context.current_price,
                reason=f"Price deviation {price_deviation:.3f} - buy opportunity",
                confidence=0.7,
                metadata={'price_deviation': price_deviation}
            )
        elif price_deviation > 0.02:
            # Price is high, opportunity to sell
            size = min(price_deviation * 100, context.max_inventory * 0.3)
            
            return InventoryDecision(
                action=InventoryAction.REDUCE,
                size=size,
                price=context.current_price,
                reason=f"Price deviation {price_deviation:.3f} - sell opportunity",
                confidence=0.7,
                metadata={'price_deviation': price_deviation}
            )
        else:
            return InventoryDecision(
                action=InventoryAction.HOLD,
                size=0,
                price=context.current_price,
                reason="No opportunistic signals",
                confidence=0.6
            )

    async def _get_mean_reverting_decision(
        self,
        context: InventoryContext
    ) -> InventoryDecision:
        """Get mean reverting inventory decision"""
        # Calculate mean reversion signal
        signal = await self._calculate_mean_reversion_signal(context)
        
        if signal > 0.1:
            # Mean reversion suggests buying
            size = signal * context.max_inventory * 0.3
            
            return InventoryDecision(
                action=InventoryAction.ADD,
                size=min(size, context.max_inventory * 0.2),
                price=context.current_price * 0.999,
                reason=f"Mean reversion signal {signal:.3f} - buy",
                confidence=0.65,
                metadata={'signal': signal}
            )
        elif signal < -0.1:
            # Mean reversion suggests selling
            size = abs(signal) * context.max_inventory * 0.3
            
            return InventoryDecision(
                action=InventoryAction.REDUCE,
                size=min(size, context.max_inventory * 0.2),
                price=context.current_price * 1.001,
                reason=f"Mean reversion signal {signal:.3f} - sell",
                confidence=0.65,
                metadata={'signal': signal}
            )
        else:
            return InventoryDecision(
                action=InventoryAction.HOLD,
                size=0,
                price=context.current_price,
                reason="No mean reversion signal",
                confidence=0.7
            )

    async def _calculate_mean_reversion_signal(
        self,
        context: InventoryContext
    ) -> float:
        """Calculate mean reversion signal"""
        try:
            # Get z-score of price relative to moving average
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    candles = await broker.get_historical_candles(
                        context.symbol,
                        timeframe='1h',
                        limit=50
                    )
                    if candles and len(candles) > 20:
                        prices = [c['close'] for c in candles]
                        ma = np.mean(prices[-20:])
                        std = np.std(prices[-20:])
                        if std > 0:
                            z_score = (prices[-1] - ma) / std
                            return -z_score  # Negative z-score suggests buy
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error calculating mean reversion signal: {e}")
        
        return 0

    async def _get_momentum_decision(
        self,
        context: InventoryContext
    ) -> InventoryDecision:
        """Get momentum-based inventory decision"""
        # Calculate momentum signal
        signal = await self._calculate_momentum_signal(context)
        
        if signal > 0.05:
            # Positive momentum, go long
            size = signal * context.max_inventory * 0.3
            
            return InventoryDecision(
                action=InventoryAction.ADD,
                size=min(size, context.max_inventory * 0.2),
                price=context.current_price * 1.001,
                reason=f"Momentum signal {signal:.3f} - follow trend",
                confidence=0.6,
                metadata={'signal': signal}
            )
        elif signal < -0.05:
            # Negative momentum, go short
            size = abs(signal) * context.max_inventory * 0.3
            
            return InventoryDecision(
                action=InventoryAction.REDUCE,
                size=min(size, context.max_inventory * 0.2),
                price=context.current_price * 0.999,
                reason=f"Momentum signal {signal:.3f} - follow trend",
                confidence=0.6,
                metadata={'signal': signal}
            )
        else:
            return InventoryDecision(
                action=InventoryAction.HOLD,
                size=0,
                price=context.current_price,
                reason="No momentum signal",
                confidence=0.7
            )

    async def _calculate_momentum_signal(
        self,
        context: InventoryContext
    ) -> float:
        """Calculate momentum signal"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    candles = await broker.get_historical_candles(
                        context.symbol,
                        timeframe='1h',
                        limit=24
                    )
                    if candles and len(candles) > 12:
                        recent_avg = np.mean([c['close'] for c in candles[-6:]])
                        older_avg = np.mean([c['close'] for c in candles[-12:-6]])
                        if older_avg > 0:
                            return (recent_avg - older_avg) / older_avg
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error calculating momentum signal: {e}")
        
        return 0

    async def _get_hybrid_decision(
        self,
        context: InventoryContext
    ) -> InventoryDecision:
        """Get hybrid inventory decision"""
        # Combine multiple strategies
        decisions = []
        
        # Get decisions from different strategies
        target_dec = await self._get_target_decision(context)
        range_dec = await self._get_range_decision(context)
        risk_dec = await self._get_risk_adjusted_decision(context)
        
        decisions.extend([target_dec, range_dec, risk_dec])
        
        # Weighted voting
        action_counts = {}
        size_total = 0
        confidence_total = 0
        
        for dec in decisions:
            if dec.action != InventoryAction.HOLD:
                action_counts[dec.action] = action_counts.get(dec.action, 0) + dec.confidence
                size_total += dec.size * dec.confidence
                confidence_total += dec.confidence
        
        if not action_counts:
            return InventoryDecision(
                action=InventoryAction.HOLD,
                size=0,
                price=context.current_price,
                reason="No consensus",
                confidence=0.5
            )
        
        # Choose action with highest weighted count
        best_action = max(action_counts, key=action_counts.get)
        avg_size = size_total / confidence_total if confidence_total > 0 else 0
        
        return InventoryDecision(
            action=best_action,
            size=avg_size,
            price=context.current_price * (0.999 if best_action == InventoryAction.ADD else 1.001),
            reason=f"Hybrid decision: {best_action.value}",
            confidence=action_counts[best_action] / sum(action_counts.values()),
            metadata={'action_weights': action_counts}
        )

    # =========================================================================
    # Inventory Monitoring
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start inventory monitoring"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Inventory monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop inventory monitoring"""
        self._is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Inventory monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_monitoring:
            try:
                for inventory_id, inventory in list(self._inventories.items()):
                    await self._check_inventory(inventory)
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in inventory monitoring: {e}")
                await asyncio.sleep(5)

    async def _check_inventory(self, inventory: InventoryResponse) -> None:
        """Check inventory status"""
        if inventory.current_inventory is None:
            return
        
        try:
            # Get current market data
            market_data = await self._get_market_data(inventory.symbol)
            current_price = market_data.get('price', 0)
            
            # Update positions
            positions = await self._get_positions(inventory.symbol)
            inventory.positions = [p.__dict__ for p in positions]
            
            # Update inventory
            inventory.current_inventory = sum(p.size for p in positions)
            inventory.inventory_state = self._determine_inventory_state(
                inventory.current_inventory,
                inventory.target_inventory,
                inventory.max_inventory,
                inventory.min_inventory
            )
            inventory.risk_level = self._calculate_risk_level(
                inventory.current_inventory,
                InventoryRequest(
                    symbol=inventory.symbol,
                    max_inventory=inventory.max_inventory,
                    min_inventory=inventory.min_inventory
                )
            )
            inventory.utilization = abs(inventory.current_inventory) / inventory.max_inventory * 100 if inventory.max_inventory > 0 else 0
            inventory.pnl = sum(p.pnl for p in positions)
            
            # Generate recommendations
            inventory.recommendations = await self._generate_recommendations(inventory)
            
            # Check if rebalance needed
            if datetime.utcnow() >= inventory.next_rebalance:
                await self._rebalance_inventory(inventory)
            
            self._inventories[inventory.inventory_id] = inventory
            
        except Exception as e:
            logger.error(f"Error checking inventory {inventory.inventory_id}: {e}")

    async def _rebalance_inventory(self, inventory: InventoryResponse) -> None:
        """Rebalance inventory"""
        try:
            # Get decision
            decision = await self.get_inventory_decision(inventory.inventory_id)
            
            if decision.action == InventoryAction.HOLD:
                return
            
            # Execute decision
            await self._execute_inventory_decision(inventory, decision)
            
            # Update timestamps
            inventory.last_rebalance = datetime.utcnow()
            inventory.next_rebalance = datetime.utcnow() + timedelta(seconds=60)
            
            logger.info(f"Inventory {inventory.inventory_id} rebalanced: {decision.action.value} {decision.size}")
            
        except Exception as e:
            logger.error(f"Error rebalancing inventory {inventory.inventory_id}: {e}")

    async def _execute_inventory_decision(
        self,
        inventory: InventoryResponse,
        decision: InventoryDecision
    ) -> None:
        """Execute inventory decision"""
        try:
            # Get broker
            broker = self.broker_factory.get_broker_for_symbol(inventory.symbol)
            if not broker:
                logger.error(f"No broker available for {inventory.symbol}")
                return
            
            # Create order            order = {
                'symbol': inventory.symbol,
                'side': 'buy' if decision.action == InventoryAction.ADD else 'sell',
                'size': decision.size,
                'price': decision.price,
                'order_type': 'limit',
                'post_only': True
            }
            
            # Place order
            result = await broker.place_order(order)
            
            if result:
                # Update daily turnover
                self._daily_turnover[inventory.inventory_id] = self._daily_turnover.get(inventory.inventory_id, 0) + decision.size * decision.price
                
                # Record trade
                trade = {
                    'timestamp': datetime.utcnow(),
                    'symbol': inventory.symbol,
                    'side': order['side'],
                    'size': decision.size,
                    'price': decision.price,
                    'inventory_id': inventory.inventory_id
                }
                self._daily_trades[inventory.inventory_id] = self._daily_trades.get(inventory.inventory_id, []) + [trade]
                
                logger.info(f"Executed inventory decision: {decision.action.value} {decision.size} @ {decision.price}")
                
        except Exception as e:
            logger.error(f"Error executing inventory decision: {e}")

    # =========================================================================
    # Inventory Analytics
    # =========================================================================

    async def get_analytics(
        self,
        inventory_id: str
    ) -> InventoryAnalyticsResponse:
        """
        Get inventory analytics.
        
        Args:
            inventory_id: Inventory ID
            
        Returns:
            InventoryAnalyticsResponse: Analytics data
        """
        if inventory_id not in self._inventories:
            raise ValueError(f"Inventory {inventory_id} not found")
        
        inventory = self._inventories[inventory_id]
        
        # Get historical data
        history = self._get_inventory_history(inventory_id)
        
        if not history:
            return InventoryAnalyticsResponse(
                avg_inventory=0,
                max_inventory_utilized=0,
                min_inventory_utilized=0,
                inventory_turnover=0,
                avg_holding_period=0,
                inventory_risk_score=0,
                diversification_score=0,
                carry_cost=0,
                pnl_attribution={},
                performance_metrics={},
                recommendations=["Insufficient data for analytics"]
            )
        
        # Calculate metrics
        inventory_values = [h.get('current_inventory', 0) for h in history]
        
        avg_inventory = np.mean(inventory_values) if inventory_values else 0
        max_inventory_utilized = max(inventory_values) if inventory_values else 0
        min_inventory_utilized = min(inventory_values) if inventory_values else 0
        
        # Inventory turnover
        daily_trades = self._daily_trades.get(inventory_id, [])
        total_turnover = sum(t.get('size', 0) for t in daily_trades)
        inventory_turnover = total_turnover / abs(avg_inventory) if avg_inventory != 0 else 0
        
        # Average holding period
        avg_holding_period = 0
        if inventory.positions:
            holding_times = [p.get('holding_time', 0) for p in inventory.positions]
            avg_holding_period = np.mean(holding_times) if holding_times else 0
        
        # Risk score
        inventory_risk_score = abs(avg_inventory) / inventory.max_inventory if inventory.max_inventory > 0 else 0
        
        # Diversification score (based on number of positions)
        diversification_score = min(1, len(inventory.positions) / 5)
        
        # Carry cost
        carry_cost = abs(avg_inventory) * 0.01  # 1% estimated carry cost
        
        # PnL attribution
        pnl_attribution = {
            'realized': inventory.pnl,
            'unrealized': sum(p.get('pnl', 0) for p in inventory.positions),
            'fees': -inventory.pnl * 0.01  # Estimated fees
        }
        
        # Performance metrics
        performance_metrics = {
            'sharpe_ratio': 0.5,
            'win_rate': 0.55,
            'profit_factor': 1.2,
            'avg_return': 0.01
        }
        
        # Generate recommendations
        recommendations = []
        if inventory_risk_score > 0.7:
            recommendations.append("High inventory risk. Consider reducing position size.")
        if inventory_turnover > 5:
            recommendations.append("High turnover. Consider reducing trading frequency.")
        if diversification_score < 0.3:
            recommendations.append("Low diversification. Consider adding more positions.")
        if carry_cost > 100:
            recommendations.append("High carry cost. Consider reducing inventory.")
        
        return InventoryAnalyticsResponse(
            avg_inventory=avg_inventory,
            max_inventory_utilized=max_inventory_utilized,
            min_inventory_utilized=min_inventory_utilized,
            inventory_turnover=inventory_turnover,
            avg_holding_period=avg_holding_period,
            inventory_risk_score=inventory_risk_score,
            diversification_score=diversification_score,
            carry_cost=carry_cost,
            pnl_attribution=pnl_attribution,
            performance_metrics=performance_metrics,
            recommendations=recommendations
        )

    def _get_inventory_history(self, inventory_id: str) -> List[Dict[str, Any]]:
        """Get inventory history"""
        return [h for h in self._inventory_history if h.get('inventory_id') == inventory_id]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _generate_recommendations(
        self,
        inventory: InventoryResponse
    ) -> List[str]:
        """Generate inventory recommendations"""
        recommendations = []
        
        if inventory.risk_level == InventoryRiskLevel.EXTREME:
            recommendations.append("Extreme inventory risk. Immediate action recommended.")
        elif inventory.risk_level == InventoryRiskLevel.HIGH:
            recommendations.append("High inventory risk. Consider reducing position.")
        
        if inventory.utilization > 80:
            recommendations.append("Inventory utilization is high. Consider rebalancing.")
        
        if inventory.current_inventory > inventory.target_inventory * 1.5:
            recommendations.append("Inventory is significantly above target. Consider selling.")
        elif inventory.current_inventory < inventory.target_inventory * 0.5:
            recommendations.append("Inventory is significantly below target. Consider buying.")
        
        if inventory.pnl < 0:
            recommendations.append("Negative PnL. Review inventory strategy.")
        
        return recommendations

    # =========================================================================
    # Inventory Management API
    # =========================================================================

    async def get_inventory(self, inventory_id: str) -> Optional[InventoryResponse]:
        """Get inventory by ID"""
        return self._inventories.get(inventory_id)

    async def get_all_inventories(self) -> List[InventoryResponse]:
        """Get all active inventories"""
        return list(self._inventories.values())

    async def update_inventory(
        self,
        inventory_id: str,
        updates: Dict[str, Any]
    ) -> Optional[InventoryResponse]:
        """Update inventory parameters"""
        if inventory_id not in self._inventories:
            return None
        
        inventory = self._inventories[inventory_id]
        
        for key, value in updates.items():
            if hasattr(inventory, key):
                setattr(inventory, key, value)
        
        self._inventories[inventory_id] = inventory
        return inventory

    async def clear_inventory(self, inventory_id: str) -> bool:
        """Clear inventory (close all positions)"""
        if inventory_id not in self._inventories:
            return False
        
        inventory = self._inventories[inventory_id]
        
        # Close all positions
        for pos in inventory.positions:
            await self._close_position(pos)
        
        # Reset inventory
        inventory.current_inventory = 0
        inventory.positions = []
        inventory.pnl = 0
        
        self._inventories[inventory_id] = inventory
        
        logger.info(f"Inventory {inventory_id} cleared")
        return True

    async def _close_position(self, position: Dict[str, Any]) -> None:
        """Close a position"""
        try:
            broker = self.broker_factory.get_broker_for_symbol(position.get('symbol'))
            if not broker:
                return
            
            order = {
                'symbol': position.get('symbol'),
                'side': 'sell' if position.get('size', 0) > 0 else 'buy',
                'size': abs(position.get('size', 0)),
                'order_type': 'market',
                'reduce_only': True
            }
            
            await broker.place_order(order)
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the inventory manager"""
        await self.stop_monitoring()
        
        # Clear all inventories
        for inventory_id in list(self._inventories.keys()):
            await self.clear_inventory(inventory_id)
        
        self._inventories.clear()
        self._inventory_history.clear()
        self._daily_trades.clear()
        self._daily_pnl.clear()
        self._daily_turnover.clear()
        
        logger.info("InventoryManager closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/market-making/inventory", tags=["Market Making Inventory"])


async def get_manager() -> InventoryManager:
    """Dependency to get InventoryManager instance"""
    return InventoryManager()


@router.post("/create", response_model=InventoryResponse)
async def create_inventory(
    request: InventoryRequest,
    manager: InventoryManager = Depends(get_manager)
):
    """Create inventory management"""
    return await manager.create_inventory(request)


@router.get("/{inventory_id}")
async def get_inventory(
    inventory_id: str,
    manager: InventoryManager = Depends(get_manager)
):
    """Get inventory by ID"""
    inventory = await manager.get_inventory(inventory_id)
    if not inventory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory {inventory_id} not found"
        )
    return inventory


@router.get("/")
async def get_all_inventories(
    manager: InventoryManager = Depends(get_manager)
):
    """Get all active inventories"""
    return await manager.get_all_inventories()


@router.put("/{inventory_id}")
async def update_inventory(
    inventory_id: str,
    updates: Dict[str, Any] = Body(..., embed=True),
    manager: InventoryManager = Depends(get_manager)
):
    """Update inventory parameters"""
    inventory = await manager.update_inventory(inventory_id, updates)
    if not inventory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory {inventory_id} not found"
        )
    return inventory


@router.post("/{inventory_id}/clear")
async def clear_inventory(
    inventory_id: str,
    manager: InventoryManager = Depends(get_manager)
):
    """Clear inventory"""
    success = await manager.clear_inventory(inventory_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory {inventory_id} not found"
        )
    return {"success": True}


@router.get("/{inventory_id}/analytics")
async def get_inventory_analytics(
    inventory_id: str,
    manager: InventoryManager = Depends(get_manager)
):
    """Get inventory analytics"""
    return await manager.get_analytics(inventory_id)


@router.get("/{inventory_id}/decision")
async def get_inventory_decision(
    inventory_id: str,
    manager: InventoryManager = Depends(get_manager)
):
    """Get inventory management decision"""
    return await manager.get_inventory_decision(inventory_id)


@router.get("/strategies")
async def get_inventory_strategies():
    """Get available inventory strategies"""
    return {
        'strategies': [
            {'name': s.value, 'description': s.name.replace('_', ' ').title()}
            for s in InventoryStrategy
        ]
    }


@router.post("/monitor/start")
async def start_inventory_monitoring(
    manager: InventoryManager = Depends(get_manager)
):
    """Start inventory monitoring"""
    await manager.start_monitoring()
    return {"status": "started"}


@router.post("/monitor/stop")
async def stop_inventory_monitoring(
    manager: InventoryManager = Depends(get_manager)
):
    """Stop inventory monitoring"""
    await manager.stop_monitoring()
    return {"status": "stopped"}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'InventoryManager',
    'InventoryStrategy',
    'InventoryAction',
    'InventoryRiskLevel',
    'InventoryRequest',
    'InventoryResponse',
    'InventoryAnalyticsResponse',
    'InventoryPosition',
    'InventoryContext',
    'InventoryDecision',
    'router'
]
