"""
NEXUS AI TRADING SYSTEM - Market Making Spread Manager Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/market-making/spread_manager.py
Description: Advanced spread management for market making with full API integration
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
from scipy import stats
from scipy.optimize import minimize_scalar
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.market_making_config import MarketMakingConfig
from shared.configs.spread_config import SpreadConfig
from shared.constants.trading_constants import TIME_FRAMES
from shared.helpers.trading_helpers import (
    calculate_volatility,
    calculate_atr,
    calculate_skew,
    calculate_bid_ask_spread
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.order_repository import OrderRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Market making imports
from trading.market_making.analytics import MarketMakingAnalytics
from trading.market_making.pricing import PricingManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class SpreadStrategy(str, Enum):
    """Spread strategies"""
    FIXED = "fixed"  # Fixed spread
    VOLATILITY = "volatility"  # Volatility-based
    DYNAMIC = "dynamic"  # Dynamic adjustment
    ADAPTIVE = "adaptive"  # Adaptive to market conditions
    INVENTORY = "inventory"  # Inventory-based
    RISK_ADJUSTED = "risk_adjusted"  # Risk-adjusted
    MACHINE_LEARNING = "machine_learning"  # ML-based
    OPTIMAL = "optimal"  # Optimal spread
    HYBRID = "hybrid"  # Hybrid approach


class SpreadAdjustmentType(str, Enum):
    """Types of spread adjustments"""
    VOLATILITY = "volatility"
    INVENTORY = "inventory"
    ORDER_FLOW = "order_flow"
    MARKET_IMPACT = "market_impact"
    COMPETITION = "competition"
    NEWS = "news"
    SENTIMENT = "sentiment"
    TIME = "time"
    RISK = "risk"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class SpreadRequest(BaseModel):
    """Request model for spread calculation"""
    symbol: str
    base_price: float
    strategy: SpreadStrategy = SpreadStrategy.VOLATILITY
    min_spread: Optional[float] = None
    max_spread: Optional[float] = None
    target_spread: Optional[float] = None
    lookback_period: int = 100
    time_horizon: str = "1d"
    include_volatility: bool = True
    include_inventory: bool = True
    risk_adjustment: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('base_price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Base price must be positive")
        return v


class SpreadResponse(BaseModel):
    """Response model for spread calculation"""
    symbol: str
    strategy: SpreadStrategy
    bid_price: float
    ask_price: float
    spread: float
    spread_pct: float
    mid_price: float
    min_spread: float
    max_spread: float
    target_spread: float
    adjustments: List[Dict[str, Any]]
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpreadAnalyticsResponse(BaseModel):
    """Response model for spread analytics"""
    avg_spread: float
    min_spread: float
    max_spread: float
    median_spread: float
    std_spread: float
    spread_distribution: Dict[str, float]
    spread_volatility: float
    spread_efficiency: float
    spread_skew: float
    spread_kurtosis: float
    recommendations: List[str]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SpreadContext:
    """Context for spread calculations"""
    symbol: str
    strategy: SpreadStrategy
    base_price: float
    current_price: float
    volatility: float
    volume: float
    order_flow: Dict[str, Any]
    inventory: float
    market_trend: str
    competition_spread: float
    timestamp: datetime
    historical_spreads: List[float]
    historical_prices: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpreadResult:
    """Result of spread calculation"""
    bid_price: float
    ask_price: float
    spread: float
    spread_pct: float
    adjustments: List[Dict[str, Any]]
    confidence: float
    model_params: Dict[str, Any]


@dataclass
class SpreadLimit:
    """Spread limits"""
    min_spread: float
    max_spread: float
    target_spread: float
    current_spread: float
    deviation: float
    status: str


# =============================================================================
# SPREAD MANAGER
# =============================================================================

class SpreadManager:
    """
    Advanced Spread Manager for Market Making with full API integration.
    
    Features:
    - Multiple spread strategies
    - Real-time spread calculation
    - Dynamic adjustment
    - Volatility-based spread
    - Inventory-based spread
    - Risk-adjusted spread
    - Optimal spread finding
    - Adaptive spread management
    - Spread analytics
    """

    def __init__(
        self,
        config: Optional[SpreadConfig] = None,
        market_making_config: Optional[MarketMakingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        analytics: Optional[MarketMakingAnalytics] = None,
        pricing_manager: Optional[PricingManager] = None
    ):
        """
        Initialize SpreadManager.
        
        Args:
            config: Spread configuration
            market_making_config: Market making configuration
            broker_factory: Factory for broker instances
            order_repo: Order repository
            trade_repo: Trade repository
            analytics: Market making analytics
            pricing_manager: Pricing manager
        """
        self.config = config or SpreadConfig()
        self.mm_config = market_making_config or MarketMakingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.analytics = analytics or MarketMakingAnalytics()
        self.pricing_manager = pricing_manager or PricingManager()
        
        # Spread history
        self._spread_history: Dict[str, List[SpreadResult]] = {}
        self._adjustment_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Spread limits
        self._spread_limits: Dict[str, SpreadLimit] = {}
        
        # Cache
        self._spread_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("SpreadManager initialized")

    # =========================================================================
    # Spread Calculation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def calculate_spread(
        self,
        request: SpreadRequest
    ) -> SpreadResponse:
        """
        Calculate spread using specified strategy.
        
        Args:
            request: Spread request
            
        Returns:
            SpreadResponse: Spread calculation results
        """
        try:
            # Build context
            context = await self._build_context(request)
            
            # Calculate spread based on strategy
            if request.strategy == SpreadStrategy.FIXED:
                result = await self._calculate_fixed_spread(context)
            elif request.strategy == SpreadStrategy.VOLATILITY:
                result = await self._calculate_volatility_spread(context)
            elif request.strategy == SpreadStrategy.DYNAMIC:
                result = await self._calculate_dynamic_spread(context)
            elif request.strategy == SpreadStrategy.ADAPTIVE:
                result = await self._calculate_adaptive_spread(context)
            elif request.strategy == SpreadStrategy.INVENTORY:
                result = await self._calculate_inventory_spread(context)
            elif request.strategy == SpreadStrategy.RISK_ADJUSTED:
                result = await self._calculate_risk_adjusted_spread(context)
            elif request.strategy == SpreadStrategy.MACHINE_LEARNING:
                result = await self._calculate_ml_spread(context)
            elif request.strategy == SpreadStrategy.OPTIMAL:
                result = await self._calculate_optimal_spread(context)
            elif request.strategy == SpreadStrategy.HYBRID:
                result = await self._calculate_hybrid_spread(context)
            else:
                result = await self._calculate_volatility_spread(context)
            
            # Store history
            self._spread_history.setdefault(request.symbol, []).append(result)
            
            # Create response
            response = SpreadResponse(
                symbol=request.symbol,
                strategy=request.strategy,
                bid_price=result.bid_price,
                ask_price=result.ask_price,
                spread=result.spread,
                spread_pct=result.spread_pct,
                mid_price=(result.bid_price + result.ask_price) / 2,
                min_spread=request.min_spread or self.config.min_spread,
                max_spread=request.max_spread or self.config.max_spread,
                target_spread=request.target_spread or self.config.target_spread,
                adjustments=result.adjustments,
                confidence=result.confidence,
                timestamp=datetime.utcnow(),
                metadata=request.metadata
            )
            
            # Cache
            self._spread_cache[request.symbol] = {
                'response': response,
                'context': context,
                'timestamp': datetime.utcnow()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error calculating spread: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Spread calculation failed: {str(e)}"
            )

    async def _build_context(self, request: SpreadRequest) -> SpreadContext:
        """Build spread context"""
        # Get market data
        market_data = await self._get_market_data(request.symbol)
        current_price = market_data.get('price', request.base_price)
        volatility = market_data.get('volatility', 0.02)
        volume = market_data.get('volume', 0)
        
        # Get order flow
        order_flow = await self._get_order_flow(request.symbol)
        
        # Get inventory
        inventory = await self._get_inventory(request.symbol)
        
        # Get market trend
        market_trend = await self._get_market_trend(request.symbol)
        
        # Get competition spread
        competition_spread = await self._get_competition_spread(request.symbol)
        
        # Get historical spreads
        historical_spreads = self._spread_history.get(request.symbol, [])
        historical_spread_values = [s.spread for s in historical_spreads[-100:]]
        
        # Get historical prices
        historical_prices = await self._get_historical_prices(
            request.symbol,
            request.lookback_period
        )
        
        return SpreadContext(
            symbol=request.symbol,
            strategy=request.strategy,
            base_price=request.base_price,
            current_price=current_price,
            volatility=volatility,
            volume=volume,
            order_flow=order_flow,
            inventory=inventory,
            market_trend=market_trend,
            competition_spread=competition_spread,
            timestamp=datetime.utcnow(),
            historical_spreads=historical_spread_values,
            historical_prices=historical_prices,
            metadata=request.metadata
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

    async def _get_order_flow(self, symbol: str) -> Dict[str, Any]:
        """Get order flow data"""
        try:
            trades = await self.trade_repo.get_by_symbol(symbol, limit=100)
            
            buy_volume = sum(t.size for t in trades if t.side == 'buy')
            sell_volume = sum(t.size for t in trades if t.side == 'sell')
            
            return {
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'total_volume': buy_volume + sell_volume,
                'imbalance': (buy_volume - sell_volume) / (buy_volume + sell_volume) if buy_volume + sell_volume > 0 else 0
            }
        except Exception as e:
            logger.warning(f"Error getting order flow: {e}")
            return {'buy_volume': 0, 'sell_volume': 0, 'total_volume': 0, 'imbalance': 0}

    async def _get_inventory(self, symbol: str) -> float:
        """Get current inventory"""
        try:
            positions = await self.position_repo.get_by_symbol(symbol)
            return sum(p.size for p in positions) if positions else 0
        except Exception as e:
            logger.warning(f"Error getting inventory: {e}")
            return 0

    async def _get_market_trend(self, symbol: str) -> str:
        """Get market trend"""
        try:
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

    async def _get_competition_spread(self, symbol: str) -> float:
        """Get competition spread"""
        # Default to config value
        return self.config.competition_spread or 0.01

    async def _get_historical_prices(
        self,
        symbol: str,
        period: int
    ) -> List[float]:
        """Get historical prices"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    candles = await broker.get_historical_candles(
                        symbol,
                        timeframe='1h',
                        limit=period
                    )
                    if candles:
                        return [float(c['close']) for c in candles]
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting historical prices: {e}")
        
        return [100.0] * period

    # =========================================================================
    # Spread Strategy Implementations
    # =========================================================================

    async def _calculate_fixed_spread(self, context: SpreadContext) -> SpreadResult:
        """Calculate fixed spread"""
        spread = self.config.target_spread or 0.01
        half_spread = spread / 2
        
        bid_price = context.base_price - half_spread
        ask_price = context.base_price + half_spread
        
        return SpreadResult(
            bid_price=bid_price,
            ask_price=ask_price,
            spread=spread,
            spread_pct=spread / context.base_price if context.base_price > 0 else 0,
            adjustments=[],
            confidence=1.0,
            model_params={'type': 'fixed', 'spread': spread}
        )

    async def _calculate_volatility_spread(
        self,
        context: SpreadContext
    ) -> SpreadResult:
        """Calculate volatility-based spread"""
        # Base spread
        base_spread = self.config.target_spread or 0.01
        
        # Adjust for volatility
        volatility = context.volatility
        vol_factor = 1 + volatility * 10  # Scale factor
        
        spread = base_spread * vol_factor
        
        # Apply min/max
        spread = max(self.config.min_spread, min(spread, self.config.max_spread))
        
        # Calculate bid/ask
        half_spread = spread / 2
        bid_price = context.base_price - half_spread
        ask_price = context.base_price + half_spread
        
        return SpreadResult(
            bid_price=bid_price,
            ask_price=ask_price,
            spread=spread,
            spread_pct=spread / context.base_price if context.base_price > 0 else 0,
            adjustments=[{
                'type': 'volatility',
                'factor': vol_factor,
                'volatility': volatility
            }],
            confidence=0.9,
            model_params={'type': 'volatility', 'volatility': volatility}
        )

    async def _calculate_dynamic_spread(self, context: SpreadContext) -> SpreadResult:
        """Calculate dynamic spread based on market conditions"""
        # Start with volatility-based spread
        base_result = await self._calculate_volatility_spread(context)
        spread = base_result.spread
        
        # Adjust for market trend
        if context.market_trend == 'uptrend':
            # Wider spread in uptrend to capture more profit
            spread *= 1.1
            adjustments = [{'type': 'trend', 'value': 'uptrend', 'factor': 1.1}]
        elif context.market_trend == 'downtrend':
            # Tighter spread in downtrend to maintain liquidity
            spread *= 0.9
            adjustments = [{'type': 'trend', 'value': 'downtrend', 'factor': 0.9}]
        else:
            adjustments = []
        
        # Adjust for order flow imbalance
        imbalance = context.order_flow.get('imbalance', 0)
        if abs(imbalance) > 0.3:
            # Significant imbalance - adjust spread
            spread *= (1 + abs(imbalance) * 0.5)
            adjustments.append({
                'type': 'order_flow',
                'imbalance': imbalance,
                'factor': 1 + abs(imbalance) * 0.5
            })
        
        # Apply min/max
        spread = max(self.config.min_spread, min(spread, self.config.max_spread))
        
        # Calculate bid/ask with skew
        skew = self._calculate_skew(context)
        half_spread = spread / 2
        bid_price = context.base_price - half_spread * (1 + skew)
        ask_price = context.base_price + half_spread * (1 - skew)
        
        return SpreadResult(
            bid_price=bid_price,
            ask_price=ask_price,
            spread=spread,
            spread_pct=spread / context.base_price if context.base_price > 0 else 0,
            adjustments=adjustments,
            confidence=0.85,
            model_params={'type': 'dynamic', 'skew': skew}
        )

    async def _calculate_adaptive_spread(self, context: SpreadContext) -> SpreadResult:
        """Calculate adaptive spread using historical performance"""
        # Get historical spreads
        historical = context.historical_spreads
        
        if len(historical) < 10:
            return await self._calculate_volatility_spread(context)
        
        # Calculate optimal spread from history
        optimal_spread = np.mean(historical[-20:]) if len(historical) >= 20 else np.mean(historical)
        
        # Adjust based on recent performance
        recent = historical[-10:] if len(historical) >= 10 else historical
        recent_avg = np.mean(recent)
        
        # If recent spread is higher, reduce to optimize
        if recent_avg > optimal_spread * 1.1:
            spread = optimal_spread * 0.95
        elif recent_avg < optimal_spread * 0.9:
            spread = optimal_spread * 1.05
        else:
            spread = optimal_spread
        
        # Apply volatility adjustment
        volatility = context.volatility
        spread *= (1 + volatility * 5)
        
        # Apply min/max
        spread = max(self.config.min_spread, min(spread, self.config.max_spread))
        
        half_spread = spread / 2
        bid_price = context.base_price - half_spread
        ask_price = context.base_price + half_spread
        
        return SpreadResult(
            bid_price=bid_price,
            ask_price=ask_price,
            spread=spread,
            spread_pct=spread / context.base_price if context.base_price > 0 else 0,
            adjustments=[{
                'type': 'adaptive',
                'historical_avg': optimal_spread,
                'recent_avg': recent_avg
            }],
            confidence=0.8,
            model_params={'type': 'adaptive', 'optimal_spread': optimal_spread}
        )

    async def _calculate_inventory_spread(self, context: SpreadContext) -> SpreadResult:
        """Calculate inventory-based spread"""
        # Start with volatility spread
        base_result = await self._calculate_volatility_spread(context)
        spread = base_result.spread
        
        # Adjust for inventory
        inventory = context.inventory
        inventory_ratio = inventory / self.config.max_inventory if self.config.max_inventory > 0 else 0
        
        if abs(inventory_ratio) > 0.3:
            # Significant inventory - adjust spread
            spread *= (1 + abs(inventory_ratio) * 0.5)
        
        # Apply min/max
        spread = max(self.config.min_spread, min(spread, self.config.max_spread))
        
        # Calculate bid/ask with inventory skew
        skew = self._calculate_inventory_skew(context)
        half_spread = spread / 2
        bid_price = context.base_price - half_spread * (1 + skew)
        ask_price = context.base_price + half_spread * (1 - skew)
        
        return SpreadResult(
            bid_price=bid_price,
            ask_price=ask_price,
            spread=spread,
            spread_pct=spread / context.base_price if context.base_price > 0 else 0,
            adjustments=[{
                'type': 'inventory',
                'inventory': inventory,
                'inventory_ratio': inventory_ratio,
                'skew': skew
            }],
            confidence=0.85,
            model_params={'type': 'inventory', 'inventory_ratio': inventory_ratio}
        )

    def _calculate_skew(self, context: SpreadContext) -> float:
        """Calculate skew based on order flow and inventory"""
        # Order flow skew
        imbalance = context.order_flow.get('imbalance', 0)
        flow_skew = imbalance * 0.5
        
        # Inventory skew
        inventory = context.inventory
        inventory_target = 0
        inventory_skew = (inventory - inventory_target) / self.config.max_inventory if self.config.max_inventory > 0 else 0
        inventory_skew = max(-0.5, min(0.5, inventory_skew))
        
        # Combine
        skew = flow_skew * 0.6 + inventory_skew * 0.4
        return max(-0.5, min(0.5, skew))

    def _calculate_inventory_skew(self, context: SpreadContext) -> float:
        """Calculate inventory skew"""
        inventory = context.inventory
        inventory_target = 0
        
        if self.config.max_inventory > 0:
            skew = (inventory - inventory_target) / self.config.max_inventory
            return max(-0.5, min(0.5, skew))
        
        return 0

    async def _calculate_risk_adjusted_spread(
        self,
        context: SpreadContext
    ) -> SpreadResult:
        """Calculate risk-adjusted spread"""
        # Start with volatility spread
        base_result = await self._calculate_volatility_spread(context)
        spread = base_result.spread
        
        # Adjust for risk
        risk_factor = 1 + context.volatility * 5
        
        # Add risk premium
        spread *= risk_factor
        
        # Adjust for inventory risk
        inventory_ratio = context.inventory / self.config.max_inventory if self.config.max_inventory > 0 else 0
        spread *= (1 + abs(inventory_ratio) * 0.3)
        
        # Apply min/max
        spread = max(self.config.min_spread, min(spread, self.config.max_spread))
        
        half_spread = spread / 2
        bid_price = context.base_price - half_spread
        ask_price = context.base_price + half_spread
        
        return SpreadResult(
            bid_price=bid_price,
            ask_price=ask_price,
            spread=spread,
            spread_pct=spread / context.base_price if context.base_price > 0 else 0,
            adjustments=[{
                'type': 'risk',
                'volatility': context.volatility,
                'inventory_ratio': inventory_ratio,
                'risk_factor': risk_factor
            }],
            confidence=0.8,
            model_params={'type': 'risk_adjusted', 'risk_factor': risk_factor}
        )

    async def _calculate_ml_spread(self, context: SpreadContext) -> SpreadResult:
        """Calculate spread using machine learning"""
        # For now, use a weighted combination of strategies
        strategies = [
            ('volatility', await self._calculate_volatility_spread(context)),
            ('inventory', await self._calculate_inventory_spread(context)),
            ('adaptive', await self._calculate_adaptive_spread(context))
        ]
        
        # Weighted average
        weights = {'volatility': 0.4, 'inventory': 0.3, 'adaptive': 0.3}
        total_weight = 0
        weighted_spread = 0
        
        for name, result in strategies:
            w = weights.get(name, 0.3)
            weighted_spread += result.spread * w
            total_weight += w
        
        spread = weighted_spread / total_weight if total_weight > 0 else self.config.target_spread
        
        # Apply min/max
        spread = max(self.config.min_spread, min(spread, self.config.max_spread))
        
        half_spread = spread / 2
        bid_price = context.base_price - half_spread
        ask_price = context.base_price + half_spread
        
        return SpreadResult(
            bid_price=bid_price,
            ask_price=ask_price,
            spread=spread,
            spread_pct=spread / context.base_price if context.base_price > 0 else 0,
            adjustments=[{
                'type': 'ml',
                'strategy_weights': weights,
                'spreads': [(name, r.spread) for name, r in strategies]
            }],
            confidence=0.75,
            model_params={'type': 'machine_learning', 'weights': weights}
        )

    async def _calculate_optimal_spread(self, context: SpreadContext) -> SpreadResult:
        """Calculate optimal spread using optimization"""
        # Define objective function: maximize expected profit
        # Expected profit = (spread - cost) * fill_probability
        
        # Estimate cost
        cost = 0.001  # Transaction cost estimate
        
        # Estimate fill probability as function of spread
        def fill_probability(spread: float) -> float:
            # Wider spread = lower fill probability
            # Normal distribution centered at target spread
            target = self.config.target_spread or 0.01
            sigma = 0.005
            return np.exp(-((spread - target) ** 2) / (2 * sigma ** 2))
        
        # Objective: profit = (spread - cost) * fill_probability(spread)
        def objective(spread: float) -> float:
            if spread <= cost:
                return -float('inf')
            profit = (spread - cost) * fill_probability(spread)
            return -profit  # Minimize negative profit
        
        # Find optimal spread
        result = minimize_scalar(
            objective,
            bounds=(self.config.min_spread, self.config.max_spread),
            method='bounded'
        )
        
        spread = result.x if result.success else self.config.target_spread
        
        half_spread = spread / 2
        bid_price = context.base_price - half_spread
        ask_price = context.base_price + half_spread
        
        return SpreadResult(
            bid_price=bid_price,
            ask_price=ask_price,
            spread=spread,
            spread_pct=spread / context.base_price if context.base_price > 0 else 0,
            adjustments=[{
                'type': 'optimal',
                'cost': cost,
                'fill_probability': fill_probability(spread)
            }],
            confidence=0.7,
            model_params={
                'type': 'optimal',
                'optimal_spread': spread,
                'cost': cost
            }
        )

    async def _calculate_hybrid_spread(self, context: SpreadContext) -> SpreadResult:
        """Calculate hybrid spread combining multiple strategies"""
        # Get spreads from multiple strategies
        volatility_result = await self._calculate_volatility_spread(context)
        inventory_result = await self._calculate_inventory_spread(context)
        adaptive_result = await self._calculate_adaptive_spread(context)
        
        # Combine with weights based on market conditions
        volatility_weight = 0.4
        inventory_weight = 0.3
        adaptive_weight = 0.3
        
        # Adjust weights based on conditions
        if abs(context.inventory) > self.config.max_inventory * 0.5:
            inventory_weight += 0.2
            volatility_weight -= 0.1
            adaptive_weight -= 0.1
        
        if context.volatility > 0.03:
            volatility_weight += 0.1
            inventory_weight -= 0.05
            adaptive_weight -= 0.05
        
        # Normalize weights
        total = volatility_weight + inventory_weight + adaptive_weight
        volatility_weight /= total
        inventory_weight /= total
        adaptive_weight /= total
        
        spread = (
            volatility_result.spread * volatility_weight +
            inventory_result.spread * inventory_weight +
            adaptive_result.spread * adaptive_weight
        )
        
        # Apply min/max
        spread = max(self.config.min_spread, min(spread, self.config.max_spread))
        
        # Calculate skew
        skew = self._calculate_skew(context)
        half_spread = spread / 2
        bid_price = context.base_price - half_spread * (1 + skew)
        ask_price = context.base_price + half_spread * (1 - skew)
        
        return SpreadResult(
            bid_price=bid_price,
            ask_price=ask_price,
            spread=spread,
            spread_pct=spread / context.base_price if context.base_price > 0 else 0,
            adjustments=[{
                'type': 'hybrid',
                'weights': {
                    'volatility': volatility_weight,
                    'inventory': inventory_weight,
                    'adaptive': adaptive_weight
                },
                'component_spreads': {
                    'volatility': volatility_result.spread,
                    'inventory': inventory_result.spread,
                    'adaptive': adaptive_result.spread
                }
            }],
            confidence=0.85,
            model_params={
                'type': 'hybrid',
                'weights': {
                    'volatility': volatility_weight,
                    'inventory': inventory_weight,
                    'adaptive': adaptive_weight
                }
            }
        )

    # =========================================================================
    # Spread Analytics
    # =========================================================================

    async def get_spread_analytics(
        self,
        symbol: str
    ) -> SpreadAnalyticsResponse:
        """
        Get spread analytics.
        
        Args:
            symbol: Symbol
            
        Returns:
            SpreadAnalyticsResponse: Spread analytics
        """
        history = self._spread_history.get(symbol, [])
        
        if not history:
            return SpreadAnalyticsResponse(
                avg_spread=0,
                min_spread=0,
                max_spread=0,
                median_spread=0,
                std_spread=0,
                spread_distribution={},
                spread_volatility=0,
                spread_efficiency=0,
                spread_skew=0,
                spread_kurtosis=0,
                recommendations=["Insufficient data for analytics"]
            )
        
        spreads = [r.spread for r in history[-100:]]
        spread_array = np.array(spreads)
        
        avg_spread = float(np.mean(spread_array))
        min_spread = float(np.min(spread_array))
        max_spread = float(np.max(spread_array))
        median_spread = float(np.median(spread_array))
        std_spread = float(np.std(spread_array))
        
        # Distribution
        percentiles = [25, 50, 75, 90, 95]
        spread_distribution = {}
        for p in percentiles:
            spread_distribution[f"{p}%"] = float(np.percentile(spread_array, p))
        
        # Spread volatility
        spread_volatility = float(np.std(np.diff(spread_array))) if len(spread_array) > 1 else 0
        
        # Spread efficiency (how close to min)
        if min_spread > 0:
            spread_efficiency = avg_spread / min_spread
        else:
            spread_efficiency = 1
        
        # Skew and kurtosis
        spread_skew = float(stats.skew(spread_array))
        spread_kurtosis = float(stats.kurtosis(spread_array))
        
        # Recommendations
        recommendations = []
        if spread_efficiency > 2:
            recommendations.append("Spread efficiency is low. Consider narrowing spreads.")
        if spread_volatility > 0.01:
            recommendations.append("High spread volatility. Consider stabilizing spread.")
        if abs(spread_skew) > 1:
            recommendations.append("Spread distribution is skewed. Review spread strategy.")
        if avg_spread > self.config.target_spread * 1.5:
            recommendations.append("Average spread is significantly above target. Consider adjusting.")
        
        return SpreadAnalyticsResponse(
            avg_spread=avg_spread,
            min_spread=min_spread,
            max_spread=max_spread,
            median_spread=median_spread,
            std_spread=std_spread,
            spread_distribution=spread_distribution,
            spread_volatility=spread_volatility,
            spread_efficiency=spread_efficiency,
            spread_skew=spread_skew,
            spread_kurtosis=spread_kurtosis,
            recommendations=recommendations
        )

    # =========================================================================
    # Spread Management API
    # =========================================================================

    async def get_current_spread(self, symbol: str) -> Optional[SpreadResponse]:
        """Get current spread"""
        cached = self._spread_cache.get(symbol)
        if cached and (datetime.utcnow() - cached['timestamp']).seconds < 5:
            return cached['response']
        return None

    async def update_spread_limits(
        self,
        symbol: str,
        min_spread: float,
        max_spread: float,
        target_spread: float
    ) -> bool:
        """Update spread limits"""
        try:
            self._spread_limits[symbol] = SpreadLimit(
                min_spread=min_spread,
                max_spread=max_spread,
                target_spread=target_spread,
                current_spread=0,
                deviation=0,
                status='ok'
            )
            logger.info(f"Updated spread limits for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error updating spread limits: {e}")
            return False

    async def get_spread_limits(self, symbol: str) -> Optional[SpreadLimit]:
        """Get spread limits"""
        return self._spread_limits.get(symbol)

    async def reset_history(self, symbol: str) -> bool:
        """Reset spread history"""
        try:
            if symbol in self._spread_history:
                self._spread_history[symbol] = []
            if symbol in self._adjustment_history:
                self._adjustment_history[symbol] = []
            logger.info(f"Reset spread history for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error resetting history: {e}")
            return False

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the spread manager"""
        self._spread_history.clear()
        self._adjustment_history.clear()
        self._spread_limits.clear()
        self._spread_cache.clear()
        logger.info("SpreadManager closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/market-making/spread", tags=["Market Making Spread"])


async def get_manager() -> SpreadManager:
    """Dependency to get SpreadManager instance"""
    return SpreadManager()


@router.post("/calculate", response_model=SpreadResponse)
async def calculate_spread(
    request: SpreadRequest,
    manager: SpreadManager = Depends(get_manager)
):
    """Calculate spread using specified strategy"""
    return await manager.calculate_spread(request)


@router.get("/{symbol}/current")
async def get_current_spread(
    symbol: str,
    manager: SpreadManager = Depends(get_manager)
):
    """Get current spread"""
    spread = await manager.get_current_spread(symbol)
    if not spread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No current spread for {symbol}"
        )
    return spread


@router.get("/{symbol}/analytics")
async def get_spread_analytics(
    symbol: str,
    manager: SpreadManager = Depends(get_manager)
):
    """Get spread analytics"""
    return await manager.get_spread_analytics(symbol)


@router.put("/{symbol}/limits")
async def update_spread_limits(
    symbol: str,
    min_spread: float = Body(..., embed=True),
    max_spread: float = Body(..., embed=True),
    target_spread: float = Body(..., embed=True),
    manager: SpreadManager = Depends(get_manager)
):
    """Update spread limits"""
    success = await manager.update_spread_limits(
        symbol, min_spread, max_spread, target_spread
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update spread limits"
        )
    return {"success": True}


@router.get("/{symbol}/limits")
async def get_spread_limits(
    symbol: str,
    manager: SpreadManager = Depends(get_manager)
):
    """Get spread limits"""
    limits = await manager.get_spread_limits(symbol)
    if not limits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No spread limits for {symbol}"
        )
    return limits


@router.get("/strategies")
async def get_spread_strategies():
    """Get available spread strategies"""
    return {
        'strategies': [
            {'name': s.value, 'description': s.name.replace('_', ' ').title()}
            for s in SpreadStrategy
        ]
    }


@router.post("/{symbol}/reset")
async def reset_spread_history(
    symbol: str,
    manager: SpreadManager = Depends(get_manager)
):
    """Reset spread history"""
    success = await manager.reset_history(symbol)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset history"
        )
    return {"success": True}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'SpreadManager',
    'SpreadStrategy',
    'SpreadAdjustmentType',
    'SpreadRequest',
    'SpreadResponse',
    'SpreadAnalyticsResponse',
    'SpreadContext',
    'SpreadResult',
    'SpreadLimit',
    'router'
]
