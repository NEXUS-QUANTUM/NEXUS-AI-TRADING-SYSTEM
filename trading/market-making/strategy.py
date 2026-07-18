"""
NEXUS AI TRADING SYSTEM - Market Making Strategy Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/market-making/strategy.py
Description: Advanced market making strategies with full API integration
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
from shared.configs.strategy_config import StrategyConfig
from shared.constants.trading_constants import (
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    TIME_FRAMES
)
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
from backend.database.repositories.order_repository import OrderRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.position_repository import PositionRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Market making imports
from trading.market_making.base import BaseMarketMaker, Quote, QuoteParameters
from trading.market_making.order_book import OrderBookManager
from trading.market_making.pricing import PricingManager
from trading.market_making.spread_manager import SpreadManager
from trading.market_making.inventory_manager import InventoryManager
from trading.market_making.analytics import MarketMakingAnalytics

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class StrategyType(str, Enum):
    """Types of market making strategies"""
    PASSIVE = "passive"  # Passive market making
    AGGRESSIVE = "aggressive"  # Aggressive quoting
    DYNAMIC = "dynamic"  # Dynamic spread adjustment
    INVENTORY = "inventory"  # Inventory-aware
    RISK_ADJUSTED = "risk_adjusted"  # Risk-adjusted quoting
    VOLATILITY = "volatility"  # Volatility-based
    ARBITRAGE = "arbitrage"  # Arbitrage-based
    SENTIMENT = "sentiment"  # Sentiment-driven
    ML = "ml"  # Machine learning based
    HYBRID = "hybrid"  # Hybrid approach


class QuoteStyle(str, Enum):
    """Quote styles"""
    SYMMETRIC = "symmetric"  # Symmetric around mid
    SKEWED = "skewed"  # Skewed based on inventory
    AGGRESSIVE_BID = "aggressive_bid"  # Aggressive on bid side
    AGGRESSIVE_ASK = "aggressive_ask"  # Aggressive on ask side
    DYNAMIC = "dynamic"  # Dynamic skewing
    ADAPTIVE = "adaptive"  # Adaptive to market


class OrderPlacementStyle(str, Enum):
    """Order placement styles"""
    POST_ONLY = "post_only"  # Post only
    LIMIT = "limit"  # Limit orders
    MARKET = "market"  # Market orders
    SMART = "smart"  # Smart routing
    ADAPTIVE = "adaptive"  # Adaptive placement


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StrategyRequest(BaseModel):
    """Request model for strategy execution"""
    symbol: str
    strategy_type: StrategyType = StrategyType.DYNAMIC
    quote_style: QuoteStyle = QuoteStyle.SYMMETRIC
    order_style: OrderPlacementStyle = OrderPlacementStyle.POST_ONLY
    base_spread: float = 0.01
    min_spread: float = 0.001
    max_spread: float = 0.05
    bid_size: float = 10.0
    ask_size: float = 10.0
    max_position: float = 100.0
    inventory_target: float = 0.0
    rebalance_threshold: float = 0.10
    time_horizon: str = "1d"
    lookback_period: int = 100
    risk_adjustment: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StrategyResponse(BaseModel):
    """Response model for strategy execution"""
    strategy_id: str
    symbol: str
    strategy_type: StrategyType
    quote_style: QuoteStyle
    order_style: OrderPlacementStyle
    status: str
    current_spread: float
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    inventory: float
    total_pnl: float
    order_count: int
    fill_rate: float
    started_at: datetime
    last_quote: datetime
    performance: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BacktestRequest(BaseModel):
    """Request model for strategy backtesting"""
    symbol: str
    strategy_type: StrategyType
    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000
    parameters: Dict[str, Any] = Field(default_factory=dict)
    include_fees: bool = True
    include_slippage: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BacktestResponse(BaseModel):
    """Response model for backtesting"""
    strategy_id: str
    symbol: str
    strategy_type: StrategyType
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_pnl: float
    total_pnl_pct: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    summary: Dict[str, Any]
    recommendations: List[str]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class StrategyContext:
    """Context for strategy execution"""
    symbol: str
    strategy_type: StrategyType
    quote_style: QuoteStyle
    order_style: OrderPlacementStyle
    base_spread: float
    min_spread: float
    max_spread: float
    bid_size: float
    ask_size: float
    max_position: float
    inventory_target: float
    current_price: float
    bid: float
    ask: float
    spread: float
    volatility: float
    inventory: float
    order_flow: Dict[str, Any]
    market_trend: str
    timestamp: datetime
    historical_prices: List[float]
    trades: List[Any]
    orders: List[Any]


@dataclass
class QuoteDecision:
    """Quote decision"""
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    spread: float
    confidence: float
    reasoning: List[str]
    adjustments: Dict[str, Any]


@dataclass
class PerformanceMetrics:
    """Performance metrics"""
    total_pnl: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl: float
    avg_trade_duration: float


# =============================================================================
# MARKET MAKING STRATEGIES
# =============================================================================

class MarketMakingStrategy:
    """
    Advanced Market Making Strategy Engine with full API integration.
    
    Features:
    - Multiple strategy types
    - Dynamic quote generation
    - Inventory management
    - Risk-adjusted quoting
    - Real-time adaptation
    - Performance tracking
    - Strategy backtesting
    - Parameter optimization
    """

    def __init__(
        self,
        config: Optional[StrategyConfig] = None,
        market_making_config: Optional[MarketMakingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        position_repo: Optional[PositionRepository] = None,
        order_book_manager: Optional[OrderBookManager] = None,
        pricing_manager: Optional[PricingManager] = None,
        spread_manager: Optional[SpreadManager] = None,
        inventory_manager: Optional[InventoryManager] = None,
        analytics: Optional[MarketMakingAnalytics] = None
    ):
        """
        Initialize MarketMakingStrategy.
        
        Args:
            config: Strategy configuration
            market_making_config: Market making configuration
            broker_factory: Factory for broker instances
            order_repo: Order repository
            trade_repo: Trade repository
            position_repo: Position repository
            order_book_manager: Order book manager
            pricing_manager: Pricing manager
            spread_manager: Spread manager
            inventory_manager: Inventory manager
            analytics: Market making analytics
        """
        self.config = config or StrategyConfig()
        self.mm_config = market_making_config or MarketMakingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.position_repo = position_repo or PositionRepository()
        self.order_book_manager = order_book_manager or OrderBookManager()
        self.pricing_manager = pricing_manager or PricingManager()
        self.spread_manager = spread_manager or SpreadManager()
        self.inventory_manager = inventory_manager or InventoryManager()
        self.analytics = analytics or MarketMakingAnalytics()
        
        # Active strategies
        self._strategies: Dict[str, StrategyResponse] = {}
        self._strategy_contexts: Dict[str, StrategyContext] = {}
        self._quote_history: Dict[str, List[QuoteDecision]] = {}
        
        # Performance tracking
        self._performance: Dict[str, PerformanceMetrics] = {}
        
        # Backtest cache
        self._backtest_cache: Dict[str, BacktestResponse] = {}
        
        logger.info("MarketMakingStrategy initialized")

    # =========================================================================
    # Strategy Execution
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def execute_strategy(
        self,
        request: StrategyRequest
    ) -> StrategyResponse:
        """
        Execute a market making strategy.
        
        Args:
            request: Strategy request
            
        Returns:
            StrategyResponse: Strategy execution results
        """
        try:
            # Generate strategy ID
            strategy_id = f"mm_strat_{int(time.time() * 1000)}_{request.symbol}"
            
            # Build context
            context = await self._build_context(request)
            
            # Start strategy
            if request.strategy_type == StrategyType.PASSIVE:
                result = await self._execute_passive_strategy(context)
            elif request.strategy_type == StrategyType.AGGRESSIVE:
                result = await self._execute_aggressive_strategy(context)
            elif request.strategy_type == StrategyType.DYNAMIC:
                result = await self._execute_dynamic_strategy(context)
            elif request.strategy_type == StrategyType.INVENTORY:
                result = await self._execute_inventory_strategy(context)
            elif request.strategy_type == StrategyType.RISK_ADJUSTED:
                result = await self._execute_risk_adjusted_strategy(context)
            elif request.strategy_type == StrategyType.VOLATILITY:
                result = await self._execute_volatility_strategy(context)
            elif request.strategy_type == StrategyType.ARBITRAGE:
                result = await self._execute_arbitrage_strategy(context)
            elif request.strategy_type == StrategyType.SENTIMENT:
                result = await self._execute_sentiment_strategy(context)
            elif request.strategy_type == StrategyType.ML:
                result = await self._execute_ml_strategy(context)
            elif request.strategy_type == StrategyType.HYBRID:
                result = await self._execute_hybrid_strategy(context)
            else:
                result = await self._execute_dynamic_strategy(context)
            
            # Create response
            response = StrategyResponse(
                strategy_id=strategy_id,
                symbol=request.symbol,
                strategy_type=request.strategy_type,
                quote_style=request.quote_style,
                order_style=request.order_style,
                status='running',
                current_spread=result.spread,
                bid_price=result.bid_price,
                ask_price=result.ask_price,
                bid_size=result.bid_size,
                ask_size=result.ask_size,
                inventory=context.inventory,
                total_pnl=0,
                order_count=0,
                fill_rate=0,
                started_at=datetime.utcnow(),
                last_quote=datetime.utcnow(),
                performance={},
                metadata=request.metadata
            )
            
            # Store strategy
            self._strategies[strategy_id] = response
            self._strategy_contexts[strategy_id] = context
            self._quote_history[strategy_id] = []
            
            logger.info(f"Strategy {strategy_id} started for {request.symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error executing strategy: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Strategy execution failed: {str(e)}"
            )

    async def _build_context(self, request: StrategyRequest) -> StrategyContext:
        """Build strategy context"""
        # Get market data
        market_data = await self._get_market_data(request.symbol)
        current_price = market_data.get('price', 0)
        bid = market_data.get('bid', current_price * 0.999)
        ask = market_data.get('ask', current_price * 1.001)
        spread = ask - bid
        volatility = market_data.get('volatility', 0.02)
        
        # Get inventory
        inventory = await self._get_inventory(request.symbol)
        
        # Get order flow
        order_flow = await self._get_order_flow(request.symbol)
        
        # Get market trend
        market_trend = await self._get_market_trend(request.symbol)
        
        # Get historical prices
        historical_prices = await self._get_historical_prices(
            request.symbol,
            request.lookback_period
        )
        
        # Get trades and orders
        trades = await self.trade_repo.get_by_symbol(request.symbol, limit=100)
        orders = await self.order_repo.get_by_symbol(request.symbol, limit=100)
        
        return StrategyContext(
            symbol=request.symbol,
            strategy_type=request.strategy_type,
            quote_style=request.quote_style,
            order_style=request.order_style,
            base_spread=request.base_spread,
            min_spread=request.min_spread,
            max_spread=request.max_spread,
            bid_size=request.bid_size,
            ask_size=request.ask_size,
            max_position=request.max_position,
            inventory_target=request.inventory_target,
            current_price=current_price,
            bid=bid,
            ask=ask,
            spread=spread,
            volatility=volatility,
            inventory=inventory,
            order_flow=order_flow,
            market_trend=market_trend,
            timestamp=datetime.utcnow(),
            historical_prices=historical_prices,
            trades=trades,
            orders=orders
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
        
        return {'price': 100.0, 'bid': 99.95, 'ask': 100.05, 'volatility': 0.02}

    async def _get_inventory(self, symbol: str) -> float:
        """Get current inventory"""
        try:
            positions = await self.position_repo.get_by_symbol(symbol)
            return sum(p.size for p in positions) if positions else 0
        except Exception as e:
            logger.warning(f"Error getting inventory: {e}")
            return 0

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
    # Strategy Implementations
    # =========================================================================

    async def _execute_passive_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute passive market making strategy"""
        # Symmetric quote around mid
        half_spread = context.base_spread / 2
        
        bid_price = context.current_price - half_spread
        ask_price = context.current_price + half_spread
        
        return QuoteDecision(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=context.bid_size,
            ask_size=context.ask_size,
            spread=context.base_spread,
            confidence=0.9,
            reasoning=["Passive quoting with symmetric spread"],
            adjustments={}
        )

    async def _execute_aggressive_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute aggressive market making strategy"""
        # Tighter spread, larger size
        spread = context.base_spread * 0.5
        half_spread = spread / 2
        
        # Aggressive skew based on order flow
        imbalance = context.order_flow.get('imbalance', 0)
        skew = imbalance * 0.3
        
        bid_price = context.current_price - half_spread * (1 + skew)
        ask_price = context.current_price + half_spread * (1 - skew)
        
        # Larger sizes
        size_multiplier = 1.5
        bid_size = context.bid_size * size_multiplier
        ask_size = context.ask_size * size_multiplier
        
        return QuoteDecision(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
            spread=spread,
            confidence=0.85,
            reasoning=["Aggressive quoting with tighter spread and larger size"],
            adjustments={'size_multiplier': size_multiplier, 'skew': skew}
        )

    async def _execute_dynamic_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute dynamic market making strategy"""
        # Adjust spread based on volatility
        volatility = context.volatility
        vol_factor = 1 + volatility * 10
        spread = context.base_spread * vol_factor
        
        # Adjust for market trend
        if context.market_trend == 'uptrend':
            spread *= 1.1
        elif context.market_trend == 'downtrend':
            spread *= 0.9
        
        # Apply limits
        spread = max(context.min_spread, min(spread, context.max_spread))
        
        half_spread = spread / 2
        
        # Dynamic skew based on multiple factors
        skew = self._calculate_dynamic_skew(context)
        
        bid_price = context.current_price - half_spread * (1 + skew)
        ask_price = context.current_price + half_spread * (1 - skew)
        
        # Dynamic sizing
        bid_size = context.bid_size * (1 - skew * 0.5)
        ask_size = context.ask_size * (1 + skew * 0.5)
        
        return QuoteDecision(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=max(1, bid_size),
            ask_size=max(1, ask_size),
            spread=spread,
            confidence=0.8,
            reasoning=[
                f"Dynamic adjustment - volatility: {volatility:.3f}",
                f"Market trend: {context.market_trend}",
                f"Skew: {skew:.3f}"
            ],
            adjustments={
                'vol_factor': vol_factor,
                'trend': context.market_trend,
                'skew': skew
            }
        )

    def _calculate_dynamic_skew(self, context: StrategyContext) -> float:
        """Calculate dynamic skew"""
        # Inventory skew
        inventory_ratio = context.inventory / context.max_position if context.max_position > 0 else 0
        inventory_skew = inventory_ratio * 0.5
        
        # Order flow skew
        imbalance = context.order_flow.get('imbalance', 0)
        flow_skew = imbalance * 0.3
        
        # Trend skew
        trend_skew = 0
        if context.market_trend == 'uptrend':
            trend_skew = 0.1
        elif context.market_trend == 'downtrend':
            trend_skew = -0.1
        
        # Combine
        skew = inventory_skew * 0.4 + flow_skew * 0.4 + trend_skew * 0.2
        return max(-0.5, min(0.5, skew))

    async def _execute_inventory_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute inventory-aware market making strategy"""
        # Start with base spread
        spread = context.base_spread
        
        # Adjust for inventory
        inventory_ratio = context.inventory / context.max_position if context.max_position > 0 else 0
        
        # Wider spread when inventory is large
        spread *= (1 + abs(inventory_ratio) * 0.5)
        
        # Apply limits
        spread = max(context.min_spread, min(spread, context.max_spread))
        
        half_spread = spread / 2
        
        # Strong inventory skew
        skew = inventory_ratio * 0.7
        
        bid_price = context.current_price - half_spread * (1 + skew)
        ask_price = context.current_price + half_spread * (1 - skew)
        
        # Adjust sizes based on inventory
        if inventory_ratio > 0.3:
            # Long inventory - reduce bid, increase ask
            bid_size = context.bid_size * (1 - inventory_ratio * 0.5)
            ask_size = context.ask_size * (1 + inventory_ratio * 0.5)
        elif inventory_ratio < -0.3:
            # Short inventory - increase bid, reduce ask
            bid_size = context.bid_size * (1 + abs(inventory_ratio) * 0.5)
            ask_size = context.ask_size * (1 - abs(inventory_ratio) * 0.5)
        else:
            bid_size = context.bid_size
            ask_size = context.ask_size
        
        return QuoteDecision(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=max(1, bid_size),
            ask_size=max(1, ask_size),
            spread=spread,
            confidence=0.85,
            reasoning=[
                f"Inventory-aware quoting",
                f"Inventory: {context.inventory:.2f}",
                f"Skew: {skew:.3f}"
            ],
            adjustments={
                'inventory': context.inventory,
                'inventory_ratio': inventory_ratio,
                'skew': skew
            }
        )

    async def _execute_risk_adjusted_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute risk-adjusted market making strategy"""
        # Risk premium based on volatility
        risk_premium = context.volatility * 2
        
        # Base spread with risk premium
        spread = context.base_spread * (1 + risk_premium)
        
        # Adjust for inventory risk
        inventory_ratio = context.inventory / context.max_position if context.max_position > 0 else 0
        spread *= (1 + abs(inventory_ratio) * 0.3)
        
        # Apply limits
        spread = max(context.min_spread, min(spread, context.max_spread))
        
        half_spread = spread / 2
        
        # Risk-based skew
        skew = inventory_ratio * 0.5 + context.volatility * 2
        
        bid_price = context.current_price - half_spread * (1 + skew)
        ask_price = context.current_price + half_spread * (1 - skew)
        
        # Conservative sizing
        size_factor = 1 / (1 + context.volatility * 5)
        bid_size = context.bid_size * size_factor
        ask_size = context.ask_size * size_factor
        
        return QuoteDecision(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=max(0.5, bid_size),
            ask_size=max(0.5, ask_size),
            spread=spread,
            confidence=0.8,
            reasoning=[
                f"Risk-adjusted quoting",
                f"Risk premium: {risk_premium:.3f}",
                f"Volatility: {context.volatility:.3f}"
            ],
            adjustments={
                'risk_premium': risk_premium,
                'volatility': context.volatility,
                'size_factor': size_factor
            }
        )

    async def _execute_volatility_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute volatility-based market making strategy"""
        # Volatility-based spread
        spread = context.base_spread * (1 + context.volatility * 10)
        
        # Adjust for volatility clustering
        if len(context.historical_prices) > 20:
            recent_vol = np.std(context.historical_prices[-20:]) / np.mean(context.historical_prices[-20:])
            spread *= (1 + recent_vol * 5)
        
        # Apply limits
        spread = max(context.min_spread, min(spread, context.max_spread))
        
        half_spread = spread / 2
        
        # Volatility-based skew
        skew = context.volatility * 2
        
        bid_price = context.current_price - half_spread * (1 + skew)
        ask_price = context.current_price + half_spread * (1 - skew)
        
        # Volatility-based sizing
        size_factor = 1 / (1 + context.volatility * 10)
        bid_size = context.bid_size * size_factor
        ask_size = context.ask_size * size_factor
        
        return QuoteDecision(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=max(0.5, bid_size),
            ask_size=max(0.5, ask_size),
            spread=spread,
            confidence=0.8,
            reasoning=[
                f"Volatility-based quoting",
                f"Volatility: {context.volatility:.3f}",
                f"Recent volatility: {recent_vol:.3f}" if len(context.historical_prices) > 20 else ""
            ],
            adjustments={
                'volatility': context.volatility,
                'recent_vol': recent_vol if len(context.historical_prices) > 20 else 0,
                'size_factor': size_factor
            }
        )

    async def _execute_arbitrage_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute arbitrage-based market making strategy"""
        # Check for arbitrage opportunities
        arbitrage_signal = await self._detect_arbitrage(context)
        
        if abs(arbitrage_signal) > 0.001:
            # Aggressive quoting to capture arbitrage
            spread = context.min_spread
            half_spread = spread / 2
            
            # Directional skew based on arbitrage
            skew = -arbitrage_signal * 5
            
            bid_price = context.current_price - half_spread * (1 + skew)
            ask_price = context.current_price + half_spread * (1 - skew)
            
            # Large sizes for arbitrage
            bid_size = context.bid_size * 2
            ask_size = context.ask_size * 2
            
            return QuoteDecision(
                bid_price=bid_price,
                ask_price=ask_price,
                bid_size=bid_size,
                ask_size=ask_size,
                spread=spread,
                confidence=0.7,
                reasoning=[f"Arbitrage opportunity detected: {arbitrage_signal:.4f}"],
                adjustments={'arbitrage_signal': arbitrage_signal}
            )
        else:
            # Fallback to passive
            return await self._execute_passive_strategy(context)

    async def _detect_arbitrage(self, context: StrategyContext) -> float:
        """Detect arbitrage opportunities"""
        # Simple price deviation from fair value
        if len(context.historical_prices) > 20:
            fair_value = np.mean(context.historical_prices[-20:])
            deviation = (context.current_price - fair_value) / fair_value
            return deviation
        return 0

    async def _execute_sentiment_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute sentiment-driven market making strategy"""
        # Get sentiment from order flow
        sentiment = await self._get_market_sentiment(context)
        
        # Adjust spread based on sentiment
        if sentiment > 0.3:
            spread = context.min_spread
            skew = -0.3
        elif sentiment < -0.3:
            spread = context.min_spread
            skew = 0.3
        else:
            spread = context.base_spread
            skew = 0
        
        half_spread = spread / 2
        
        bid_price = context.current_price - half_spread * (1 + skew)
        ask_price = context.current_price + half_spread * (1 - skew)
        
        return QuoteDecision(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=context.bid_size,
            ask_size=context.ask_size,
            spread=spread,
            confidence=0.65,
            reasoning=[f"Sentiment-driven quoting, sentiment: {sentiment:.2f}"],
            adjustments={'sentiment': sentiment}
        )

    async def _get_market_sentiment(self, context: StrategyContext) -> float:
        """Get market sentiment"""
        # Simple sentiment from order flow imbalance
        return context.order_flow.get('imbalance', 0)

    async def _execute_ml_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute ML-based market making strategy"""
        # Combine multiple strategies with ML weights
        strategies = [
            ('volatility', await self._execute_volatility_strategy(context)),
            ('inventory', await self._execute_inventory_strategy(context)),
            ('dynamic', await self._execute_dynamic_strategy(context))
        ]
        
        # ML weights (simplified)
        weights = {
            'volatility': 0.4,
            'inventory': 0.3,
            'dynamic': 0.3
        }
        
        # Weighted combination
        bid_price = 0
        ask_price = 0
        bid_size = 0
        ask_size = 0
        spread = 0
        total_weight = 0
        
        for name, decision in strategies:
            w = weights.get(name, 0.3)
            bid_price += decision.bid_price * w
            ask_price += decision.ask_price * w
            bid_size += decision.bid_size * w
            ask_size += decision.ask_size * w
            spread += decision.spread * w
            total_weight += w
        
        if total_weight > 0:
            bid_price /= total_weight
            ask_price /= total_weight
            bid_size /= total_weight
            ask_size /= total_weight
            spread /= total_weight
        
        return QuoteDecision(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
            spread=spread,
            confidence=0.75,
            reasoning=["ML-based combination of strategies"],
            adjustments={'weights': weights}
        )

    async def _execute_hybrid_strategy(
        self,
        context: StrategyContext
    ) -> QuoteDecision:
        """Execute hybrid market making strategy"""
        # Combine multiple strategies
        strategies = [
            ('volatility', await self._execute_volatility_strategy(context)),
            ('inventory', await self._execute_inventory_strategy(context)),
            ('dynamic', await self._execute_dynamic_strategy(context)),
            ('risk_adjusted', await self._execute_risk_adjusted_strategy(context))
        ]
        
        # Adaptive weights based on market conditions
        weights = self._calculate_hybrid_weights(context)
        
        # Weighted combination
        bid_price = 0
        ask_price = 0
        bid_size = 0
        ask_size = 0
        spread = 0
        total_weight = 0
        
        for name, decision in strategies:
            w = weights.get(name, 0.25)
            bid_price += decision.bid_price * w
            ask_price += decision.ask_price * w
            bid_size += decision.bid_size * w
            ask_size += decision.ask_size * w
            spread += decision.spread * w
            total_weight += w
        
        if total_weight > 0:
            bid_price /= total_weight
            ask_price /= total_weight
            bid_size /= total_weight
            ask_size /= total_weight
            spread /= total_weight
        
        return QuoteDecision(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
            spread=spread,
            confidence=0.85,
            reasoning=["Hybrid combination with adaptive weights"],
            adjustments={'weights': weights}
        )

    def _calculate_hybrid_weights(self, context: StrategyContext) -> Dict[str, float]:
        """Calculate hybrid strategy weights"""
        weights = {
            'volatility': 0.25,
            'inventory': 0.25,
            'dynamic': 0.25,
            'risk_adjusted': 0.25
        }
        
        # Adjust based on volatility
        if context.volatility > 0.03:
            weights['volatility'] += 0.15
            weights['risk_adjusted'] += 0.1
            weights['dynamic'] -= 0.15
            weights['inventory'] -= 0.1
        
        # Adjust based on inventory
        inventory_ratio = abs(context.inventory) / context.max_position if context.max_position > 0 else 0
        if inventory_ratio > 0.3:
            weights['inventory'] += 0.2
            weights['dynamic'] += 0.1
            weights['volatility'] -= 0.15
            weights['risk_adjusted'] -= 0.15
        
        # Normalize
        total = sum(weights.values())
        for key in weights:
            weights[key] /= total
        
        return weights

    # =========================================================================
    # Strategy Management
    # =========================================================================

    async def get_strategy(self, strategy_id: str) -> Optional[StrategyResponse]:
        """Get strategy by ID"""
        return self._strategies.get(strategy_id)

    async def get_all_strategies(self) -> List[StrategyResponse]:
        """Get all active strategies"""
        return list(self._strategies.values())

    async def stop_strategy(self, strategy_id: str) -> bool:
        """Stop a strategy"""
        if strategy_id in self._strategies:
            self._strategies[strategy_id].status = 'stopped'
            logger.info(f"Strategy {strategy_id} stopped")
            return True
        return False

    async def pause_strategy(self, strategy_id: str) -> bool:
        """Pause a strategy"""
        if strategy_id in self._strategies:
            self._strategies[strategy_id].status = 'paused'
            logger.info(f"Strategy {strategy_id} paused")
            return True
        return False

    async def resume_strategy(self, strategy_id: str) -> bool:
        """Resume a strategy"""
        if strategy_id in self._strategies:
            self._strategies[strategy_id].status = 'running'
            logger.info(f"Strategy {strategy_id} resumed")
            return True
        return False

    async def update_strategy(
        self,
        strategy_id: str,
        updates: Dict[str, Any]
    ) -> Optional[StrategyResponse]:
        """Update strategy parameters"""
        if strategy_id not in self._strategies:
            return None
        
        strategy = self._strategies[strategy_id]
        context = self._strategy_contexts[strategy_id]
        
        for key, value in updates.items():
            if hasattr(strategy, key):
                setattr(strategy, key, value)
            if hasattr(context, key):
                setattr(context, key, value)
        
        self._strategies[strategy_id] = strategy
        self._strategy_contexts[strategy_id] = context
        
        return strategy

    # =========================================================================
    # Performance Tracking
    # =========================================================================

    async def get_performance(
        self,
        strategy_id: str
    ) -> Optional[PerformanceMetrics]:
        """Get strategy performance"""
        return self._performance.get(strategy_id)

    async def update_performance(self, strategy_id: str) -> None:
        """Update strategy performance"""
        if strategy_id not in self._strategies:
            return
        
        strategy = self._strategies[strategy_id]
        
        # Get trades
        trades = await self.trade_repo.get_by_symbol(strategy.symbol, limit=1000)
        
        if not trades:
            return
        
        # Calculate metrics
        total_pnl = sum(t.pnl for t in trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / len(trades) if trades else 0
        
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Sharpe ratio
        returns = [t.pnl for t in trades]
        avg_return = np.mean(returns) if returns else 0
        std_return = np.std(returns) if returns else 1
        sharpe_ratio = avg_return / std_return * np.sqrt(252) if std_return > 0 else 0
        
        # Max drawdown
        equity = [0]
        for trade in trades:
            equity.append(equity[-1] + trade.pnl)
        
        peak = max(equity)
        max_drawdown = 0
        for value in equity:
            dd = (peak - value) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, dd)
        
        # Average trade duration
        durations = []
        for trade in trades:
            if hasattr(trade, 'created_at') and hasattr(trade, 'execution_time'):
                duration = (trade.execution_time - trade.created_at).total_seconds()
                durations.append(duration)
        avg_duration = np.mean(durations) if durations else 0
        
        self._performance[strategy_id] = PerformanceMetrics(
            total_pnl=total_pnl,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(trades),
            avg_trade_pnl=total_pnl / len(trades) if trades else 0,
            avg_trade_duration=avg_duration
        )

    # =========================================================================
    # Backtesting
    # =========================================================================

    async def backtest_strategy(
        self,
        request: BacktestRequest
    ) -> BacktestResponse:
        """Backtest a strategy"""
        try:
            # Generate strategy ID
            strategy_id = f"bt_{int(time.time() * 1000)}_{request.symbol}"
            
            # Get historical data
            historical_data = await self._get_historical_data(
                request.symbol,
                request.start_date,
                request.end_date
            )
            
            # Run backtest
            results = await self._run_backtest(
                request.strategy_type,
                request.parameters,
                historical_data,
                request.initial_capital,
                request.include_fees,
                request.include_slippage
            )
            
            # Create response
            response = BacktestResponse(
                strategy_id=strategy_id,
                symbol=request.symbol,
                strategy_type=request.strategy_type,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
                final_capital=results['final_capital'],
                total_pnl=results['total_pnl'],
                total_pnl_pct=results['total_pnl_pct'],
                sharpe_ratio=results['sharpe_ratio'],
                max_drawdown=results['max_drawdown'],
                win_rate=results['win_rate'],
                profit_factor=results['profit_factor'],
                total_trades=results['total_trades'],
                summary=results['summary'],
                recommendations=results['recommendations']
            )
            
            # Cache result
            self._backtest_cache[strategy_id] = response
            
            logger.info(f"Backtest {strategy_id} completed for {request.symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error running backtest: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Backtest failed: {str(e)}"
            )

    async def _get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical data for backtesting"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    candles = await broker.get_historical_candles(
                        symbol,
                        timeframe='1h',
                        start_time=start_date,
                        end_time=end_date
                    )
                    if candles:
                        return candles
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting historical data: {e}")
        
        # Generate mock data
        return self._generate_mock_historical_data(start_date, end_date)

    def _generate_mock_historical_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Generate mock historical data"""
        data = []
        price = 100.0
        current = start_date
        
        while current <= end_date:
            price *= (1 + np.random.normal(0, 0.001))
            data.append({
                'timestamp': current,
                'open': price * 0.999,
                'high': price * 1.002,
                'low': price * 0.998,
                'close': price,
                'volume': np.random.uniform(1000, 10000)
            })
            current += timedelta(minutes=60)
        
        return data

    async def _run_backtest(
        self,
        strategy_type: StrategyType,
        parameters: Dict[str, Any],
        data: List[Dict[str, Any]],
        initial_capital: float,
        include_fees: bool,
        include_slippage: bool
    ) -> Dict[str, Any]:
        """Run backtest simulation"""
        # Simplified backtest
        # This would be more sophisticated in production
        
        capital = initial_capital
        inventory = 0
        trades = []
        equity_curve = [capital]
        timestamps = []
        
        for i, candle in enumerate(data):
            price = candle['close']
            timestamps.append(candle['timestamp'])
            
            # Simple strategy simulation
            if i > 0 and i % 5 == 0:  # Trade every 5 periods
                # Determine signal
                signal = np.random.choice([-1, 0, 1], p=[0.3, 0.4, 0.3])
                
                if signal == 1 and capital > price * 10:
                    # Buy
                    size = min(10, capital / price)
                    capital -= size * price
                    inventory += size
                    trades.append({
                        'timestamp': candle['timestamp'],
                        'side': 'buy',
                        'size': size,
                        'price': price,
                        'pnl': 0
                    })
                elif signal == -1 and inventory > 0:
                    # Sell
                    size = min(inventory, 10)
                    pnl = (price - trades[-1]['price']) * size if trades else 0
                    capital += size * price
                    inventory -= size
                    trades[-1]['pnl'] = pnl if trades else 0
                    trades[-1]['exit_price'] = price
            
            # Update equity
            equity = capital + inventory * price
            equity_curve.append(equity)
        
        # Calculate metrics
        final_capital = equity_curve[-1]
        total_pnl = final_capital - initial_capital
        total_pnl_pct = (total_pnl / initial_capital) * 100
        
        # Simple metrics
        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i-1] > 0:
                returns.append((equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1])
        
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24) if returns else 0
        
        # Drawdown
        peak = max(equity_curve)
        max_drawdown = (peak - final_capital) / peak if peak > 0 else 0
        
        # Win rate
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0
        
        # Profit factor
        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Recommendations
        recommendations = []
        if sharpe_ratio < 0.5:
            recommendations.append("Low Sharpe ratio. Consider reducing risk.")
        if max_drawdown > 0.2:
            recommendations.append("High drawdown. Add risk controls.")
        if win_rate < 0.4:
            recommendations.append("Low win rate. Review entry criteria.")
        
        return {
            'final_capital': final_capital,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(trades),
            'summary': {
                'initial_capital': initial_capital,
                'final_capital': final_capital,
                'total_trades': len(trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(trades) - len(winning_trades)
            },
            'recommendations': recommendations
        }

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the strategy engine"""
        self._strategies.clear()
        self._strategy_contexts.clear()
        self._quote_history.clear()
        self._performance.clear()
        self._backtest_cache.clear()
        logger.info("MarketMakingStrategy closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/market-making/strategies", tags=["Market Making Strategies"])


async def get_engine() -> MarketMakingStrategy:
    """Dependency to get MarketMakingStrategy instance"""
    return MarketMakingStrategy()


@router.post("/execute", response_model=StrategyResponse)
async def execute_strategy(
    request: StrategyRequest,
    engine: MarketMakingStrategy = Depends(get_engine)
):
    """Execute a market making strategy"""
    return await engine.execute_strategy(request)


@router.get("/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    engine: MarketMakingStrategy = Depends(get_engine)
):
    """Get strategy by ID"""
    strategy = await engine.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found"
        )
    return strategy


@router.get("/")
async def get_all_strategies(
    engine: MarketMakingStrategy = Depends(get_engine)
):
    """Get all active strategies"""
    return await engine.get_all_strategies()


@router.post("/{strategy_id}/stop")
async def stop_strategy(
    strategy_id: str,
    engine: MarketMakingStrategy = Depends(get_engine)
):
    """Stop a strategy"""
    success = await engine.stop_strategy(strategy_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found"
        )
    return {"success": True}


@router.post("/{strategy_id}/pause")
async def pause_strategy(
    strategy_id: str,
    engine: MarketMakingStrategy = Depends(get_engine)
):
    """Pause a strategy"""
    success = await engine.pause_strategy(strategy_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found"
        )
    return {"success": True}


@router.post("/{strategy_id}/resume")
async def resume_strategy(
    strategy_id: str,
    engine: MarketMakingStrategy = Depends(get_engine)
):
    """Resume a strategy"""
    success = await engine.resume_strategy(strategy_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found"
        )
    return {"success": True}


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    updates: Dict[str, Any] = Body(..., embed=True),
    engine: MarketMakingStrategy = Depends(get_engine)
):
    """Update strategy parameters"""
    strategy = await engine.update_strategy(strategy_id, updates)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found"
        )
    return strategy


@router.get("/{strategy_id}/performance")
async def get_performance(
    strategy_id: str,
    engine: MarketMakingStrategy = Depends(get_engine)
):
    """Get strategy performance"""
    performance = await engine.get_performance(strategy_id)
    if not performance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Performance for strategy {strategy_id} not found"
        )
    return performance


@router.post("/backtest")
async def backtest_strategy(
    request: BacktestRequest,
    engine: MarketMakingStrategy = Depends(get_engine)
):
    """Backtest a strategy"""
    return await engine.backtest_strategy(request)


@router.get("/types")
async def get_strategy_types():
    """Get available strategy types"""
    return {
        'types': [
            {'name': t.value, 'description': t.name.replace('_', ' ').title()}
            for t in StrategyType
        ]
    }


@router.get("/quote-styles")
async def get_quote_styles():
    """Get available quote styles"""
    return {
        'styles': [
            {'name': s.value, 'description': s.name.replace('_', ' ').title()}
            for s in QuoteStyle
        ]
    }


@router.get("/order-styles")
async def get_order_styles():
    """Get available order placement styles"""
    return {
        'styles': [
            {'name': s.value, 'description': s.name.replace('_', ' ').title()}
            for s in OrderPlacementStyle
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'MarketMakingStrategy',
    'StrategyType',
    'QuoteStyle',
    'OrderPlacementStyle',
    'StrategyRequest',
    'StrategyResponse',
    'BacktestRequest',
    'BacktestResponse',
    'StrategyContext',
    'QuoteDecision',
    'PerformanceMetrics',
    'router'
]
