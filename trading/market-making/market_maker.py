"""
NEXUS AI TRADING SYSTEM - Market Maker Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/market-making/market_maker.py
Description: Core market making engine with full API integration
"""

import asyncio
import logging
import time
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
from shared.constants.trading_constants import (
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    TIME_FRAMES
)
from shared.helpers.trading_helpers import (
    calculate_spread,
    calculate_volatility,
    calculate_skew,
    calculate_atr
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Order, Trade, Position
from backend.database.repositories.order_repository import OrderRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.position_repository import PositionRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Market making imports
from trading.market_making.base import BaseMarketMaker, MarketMakingState, Quote, QuoteStatus
from trading.market_making.order_book import OrderBookManager
from trading.market_making.analytics import MarketMakingAnalytics
from trading.market_making.hedging import HedgingManager
from trading.market_making.inventory_manager import InventoryManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class MarketMakerStatus(str, Enum):
    """Market maker operational status"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"


class QuoteAdjustmentType(str, Enum):
    """Types of quote adjustments"""
    SPREAD = "spread"
    SKEW = "skew"
    SIZE = "size"
    PRICE = "price"
    INVENTORY = "inventory"
    VOLATILITY = "volatility"
    MOMENTUM = "momentum"
    RISK = "risk"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class MarketMakerRequest(BaseModel):
    """Request model for market maker"""
    symbol: str
    strategy: str = "default"
    base_spread: float = 0.01
    min_spread: float = 0.001
    max_spread: float = 0.05
    bid_size: float = 10.0
    ask_size: float = 10.0
    max_position: float = 100.0
    inventory_target: float = 0.0
    skew_factor: float = 1.0
    volatility_adjustment: bool = True
    momentum_adjustment: bool = True
    order_lifetime: int = 60  # seconds
    max_order_age: int = 300  # seconds
    rebalance_threshold: float = 0.10
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MarketMakerResponse(BaseModel):
    """Response model for market maker"""
    maker_id: str
    symbol: str
    status: MarketMakerStatus
    strategy: str
    current_spread: float
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    inventory: float
    inventory_value: float
    total_pnl: float
    active_orders: int
    quote_count: int
    fill_rate: float
    started_at: datetime
    last_quote: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QuoteRequest(BaseModel):
    """Request model for quote"""
    symbol: str
    quote_type: str = "standard"
    size_multiplier: float = 1.0
    urgency: str = "normal"  # low, normal, high, urgent
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MarketMakerContext:
    """Context for market making"""
    symbol: str
    strategy: str
    base_spread: float
    min_spread: float
    max_spread: float
    bid_size: float
    ask_size: float
    max_position: float
    inventory_target: float
    skew_factor: float
    current_price: float
    bid: float
    ask: float
    spread: float
    volatility: float
    volume: float
    market_trend: str
    inventory: float
    inventory_value: float
    timestamp: datetime


@dataclass
class QuoteResult:
    """Result of quote generation"""
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    spread: float
    adjustments: List[str]
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# MARKET MAKER ENGINE
# =============================================================================

class MarketMaker:
    """
    Core Market Maker Engine with full API integration.
    
    Features:
    - Automated quote generation
    - Dynamic spread adjustment
    - Inventory management
    - Risk management
    - Performance tracking
    - Multi-strategy support
    - Real-time monitoring
    """

    def __init__(
        self,
        config: Optional[MarketMakingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        position_repo: Optional[PositionRepository] = None,
        order_book_manager: Optional[OrderBookManager] = None,
        analytics: Optional[MarketMakingAnalytics] = None,
        hedging_manager: Optional[HedgingManager] = None,
        inventory_manager: Optional[InventoryManager] = None
    ):
        """
        Initialize MarketMaker.
        
        Args:
            config: Market making configuration
            broker_factory: Factory for broker instances
            order_repo: Order repository
            trade_repo: Trade repository
            position_repo: Position repository
            order_book_manager: Order book manager
            analytics: Market making analytics
            hedging_manager: Hedging manager
            inventory_manager: Inventory manager
        """
        self.config = config or MarketMakingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.position_repo = position_repo or PositionRepository()
        self.order_book_manager = order_book_manager or OrderBookManager()
        self.analytics = analytics or MarketMakingAnalytics()
        self.hedging_manager = hedging_manager or HedgingManager()
        self.inventory_manager = inventory_manager or InventoryManager()
        
        # Active market makers
        self._makers: Dict[str, MarketMakerResponse] = {}
        self._maker_contexts: Dict[str, MarketMakerContext] = {}
        self._active_quotes: Dict[str, Quote] = {}
        
        # Order tracking
        self._order_history: Dict[str, List[Dict[str, Any]]] = {}
        self._trade_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Monitoring
        self._is_running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Quote counter
        self._quote_counter: int = 0
        
        logger.info("MarketMaker initialized")

    # =========================================================================
    # Market Maker Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def create_market_maker(
        self,
        request: MarketMakerRequest
    ) -> MarketMakerResponse:
        """
        Create a new market maker.
        
        Args:
            request: Market maker request
            
        Returns:
            MarketMakerResponse: Created market maker
        """
        try:
            # Validate request
            await self._validate_request(request)
            
            # Generate maker ID
            maker_id = f"mm_{int(time.time() * 1000)}_{request.symbol}"
            
            # Get initial market data
            market_data = await self._get_market_data(request.symbol)
            current_price = market_data.get('price', 0)
            bid = market_data.get('bid', current_price * 0.999)
            ask = market_data.get('ask', current_price * 1.001)
            
            # Calculate initial spread
            spread = ask - bid if ask > bid else request.base_spread * current_price
            
            # Create response
            response = MarketMakerResponse(
                maker_id=maker_id,
                symbol=request.symbol,
                status=MarketMakerStatus.INITIALIZING,
                strategy=request.strategy,
                current_spread=spread,
                bid_price=bid,
                ask_price=ask,
                bid_size=request.bid_size,
                ask_size=request.ask_size,
                inventory=0,
                inventory_value=0,
                total_pnl=0,
                active_orders=0,
                quote_count=0,
                fill_rate=0,
                started_at=datetime.utcnow(),
                last_quote=datetime.utcnow(),
                metadata=request.metadata
            )
            
            # Create context
            context = MarketMakerContext(
                symbol=request.symbol,
                strategy=request.strategy,
                base_spread=request.base_spread,
                min_spread=request.min_spread,
                max_spread=request.max_spread,
                bid_size=request.bid_size,
                ask_size=request.ask_size,
                max_position=request.max_position,
                inventory_target=request.inventory_target,
                skew_factor=request.skew_factor,
                current_price=current_price,
                bid=bid,
                ask=ask,
                spread=spread,
                volatility=market_data.get('volatility', 0.02),
                volume=market_data.get('volume', 0),
                market_trend='sideways',
                inventory=0,
                inventory_value=0,
                timestamp=datetime.utcnow()
            )
            
            # Store market maker
            self._makers[maker_id] = response
            self._maker_contexts[maker_id] = context
            self._order_history[maker_id] = []
            self._trade_history[maker_id] = []
            
            # Start market maker
            await self._start_market_maker(maker_id)
            
            logger.info(f"Market maker created: {maker_id} for {request.symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error creating market maker: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Market maker creation failed: {str(e)}"
            )

    async def _validate_request(self, request: MarketMakerRequest) -> None:
        """Validate market maker request"""
        if request.base_spread <= 0:
            raise ValueError("Base spread must be positive")
        
        if request.min_spread <= 0:
            raise ValueError("Min spread must be positive")
        
        if request.max_spread <= request.min_spread:
            raise ValueError("Max spread must be greater than min spread")
        
        if request.bid_size <= 0:
            raise ValueError("Bid size must be positive")
        
        if request.ask_size <= 0:
            raise ValueError("Ask size must be positive")
        
        if request.max_position <= 0:
            raise ValueError("Max position must be positive")
        
        if request.order_lifetime < 1:
            raise ValueError("Order lifetime must be at least 1 second")

    async def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get current market data"""
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
                        'low': float(ticker.get('low', 0)),
                        'change': float(ticker.get('change', 0)),
                        'change_pct': float(ticker.get('change_pct', 0))
                    }
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting market data for {symbol}: {e}")
        
        return {'price': 100.0, 'bid': 99.95, 'ask': 100.05, 'volatility': 0.02}

    # =========================================================================
    # Market Maker Operations
    # =========================================================================

    async def _start_market_maker(self, maker_id: str) -> None:
        """Start a market maker"""
        if maker_id not in self._makers:
            return
        
        maker = self._makers[maker_id]
        maker.status = MarketMakerStatus.RUNNING
        
        # Generate initial quote
        await self._generate_quote(maker_id)
        
        logger.info(f"Market maker {maker_id} started")

    async def stop_market_maker(self, maker_id: str) -> bool:
        """
        Stop a market maker.
        
        Args:
            maker_id: Market maker ID
            
        Returns:
            bool: Success indicator
        """
        if maker_id not in self._makers:
            return False
        
        maker = self._makers[maker_id]
        maker.status = MarketMakerStatus.STOPPED
        
        # Cancel all orders
        await self._cancel_all_orders(maker_id)
        
        logger.info(f"Market maker {maker_id} stopped")
        return True

    async def pause_market_maker(self, maker_id: str) -> bool:
        """
        Pause a market maker.
        
        Args:
            maker_id: Market maker ID
            
        Returns:
            bool: Success indicator
        """
        if maker_id not in self._makers:
            return False
        
        maker = self._makers[maker_id]
        maker.status = MarketMakerStatus.PAUSED
        
        # Cancel all orders
        await self._cancel_all_orders(maker_id)
        
        logger.info(f"Market maker {maker_id} paused")
        return True

    async def resume_market_maker(self, maker_id: str) -> bool:
        """
        Resume a market maker.
        
        Args:
            maker_id: Market maker ID
            
        Returns:
            bool: Success indicator
        """
        if maker_id not in self._makers:
            return False
        
        maker = self._makers[maker_id]
        maker.status = MarketMakerStatus.RUNNING
        
        # Generate new quote
        await self._generate_quote(maker_id)
        
        logger.info(f"Market maker {maker_id} resumed")
        return True

    async def update_market_maker(
        self,
        maker_id: str,
        updates: Dict[str, Any]
    ) -> Optional[MarketMakerResponse]:
        """
        Update market maker parameters.
        
        Args:
            maker_id: Market maker ID
            updates: Updates to apply
            
        Returns:
            Optional[MarketMakerResponse]: Updated market maker
        """
        if maker_id not in self._makers:
            return None
        
        maker = self._makers[maker_id]
        context = self._maker_contexts[maker_id]
        
        # Update fields
        for key, value in updates.items():
            if hasattr(maker, key):
                setattr(maker, key, value)
            if hasattr(context, key):
                setattr(context, key, value)
        
        self._makers[maker_id] = maker
        self._maker_contexts[maker_id] = context
        
        # Regenerate quote if running
        if maker.status == MarketMakerStatus.RUNNING:
            await self._generate_quote(maker_id)
        
        logger.info(f"Market maker {maker_id} updated")
        return maker

    async def _cancel_all_orders(self, maker_id: str) -> int:
        """Cancel all orders for a market maker"""
        cancelled_count = 0
        
        try:
            # Get active orders
            orders = await self.order_repo.get_by_symbol(
                self._makers[maker_id].symbol,
                status='open'
            )
            
            for order in orders:
                # Cancel order via broker
                broker = self.broker_factory.get_broker_for_symbol(order.symbol)
                if broker:
                    success = await broker.cancel_order(order.id)
                    if success:
                        cancelled_count += 1
            
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
        
        return cancelled_count

    # =========================================================================
    # Quote Generation
    # =========================================================================

    async def generate_quote(self, maker_id: str) -> Optional[QuoteResult]:
        """
        Generate a quote for a market maker.
        
        Args:
            maker_id: Market maker ID
            
        Returns:
            Optional[QuoteResult]: Generated quote
        """
        if maker_id not in self._makers:
            return None
        
        return await self._generate_quote(maker_id)

    async def _generate_quote(self, maker_id: str) -> Optional[QuoteResult]:
        """Generate quote for market maker"""
        try:
            maker = self._makers[maker_id]
            context = self._maker_contexts[maker_id]
            
            if maker.status not in [MarketMakerStatus.RUNNING, MarketMakerStatus.DEGRADED]:
                return None
            
            # Update market data
            market_data = await self._get_market_data(maker.symbol)
            context.current_price = market_data.get('price', context.current_price)
            context.bid = market_data.get('bid', context.bid)
            context.ask = market_data.get('ask', context.ask)
            context.volatility = market_data.get('volatility', context.volatility)
            context.volume = market_data.get('volume', context.volume)
            context.timestamp = datetime.utcnow()
            
            # Get inventory
            inventory = await self._get_inventory(maker.symbol)
            context.inventory = inventory.position if inventory else 0
            context.inventory_value = inventory.value if inventory else 0
            
            # Get market trend
            context.market_trend = await self._get_market_trend(maker.symbol)
            
            # Calculate quote
            result = await self._calculate_quote(context)
            
            # Update maker
            maker.bid_price = result.bid_price
            maker.ask_price = result.ask_price
            maker.bid_size = result.bid_size
            maker.ask_size = result.ask_size
            maker.current_spread = result.spread
            maker.last_quote = datetime.utcnow()
            maker.quote_count += 1
            
            # Place orders
            await self._place_quote_orders(maker_id, result)
            
            # Store quote
            self._active_quotes[maker_id] = Quote(
                symbol=maker.symbol,
                bid_price=result.bid_price,
                ask_price=result.ask_price,
                bid_size=result.bid_size,
                ask_size=result.ask_size,
                spread=result.spread,
                mid_price=(result.bid_price + result.ask_price) / 2,
                timestamp=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=maker.order_lifetime)
            )
            
            # Update context
            self._maker_contexts[maker_id] = context
            self._makers[maker_id] = maker
            
            self._quote_counter += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating quote for {maker_id}: {e}")
            return None

    async def _calculate_quote(self, context: MarketMakerContext) -> QuoteResult:
        """Calculate quote based on context"""
        adjustments = []
        
        # Base spread
        spread = context.base_spread * context.current_price
        
        # Adjust for volatility
        if context.volatility > 0:
            vol_factor = 1 + context.volatility * 5  # Scale factor
            spread = max(context.min_spread, min(spread * vol_factor, context.max_spread))
            adjustments.append(QuoteAdjustmentType.VOLATILITY.value)
        
        # Adjust for inventory
        inventory_ratio = context.inventory / context.max_position if context.max_position > 0 else 0
        skew = context.skew_factor * inventory_ratio
        
        # Price adjustment based on inventory skew
        bid_price = context.current_price - spread / 2 - skew * spread * 0.5
        ask_price = context.current_price + spread / 2 - skew * spread * 0.5
        
        # Adjust for market trend
        if context.market_trend == 'uptrend':
            bid_price += context.current_price * 0.001
            ask_price += context.current_price * 0.001
            adjustments.append(QuoteAdjustmentType.MOMENTUM.value)
        elif context.market_trend == 'downtrend':
            bid_price -= context.current_price * 0.001
            ask_price -= context.current_price * 0.001
            adjustments.append(QuoteAdjustmentType.MOMENTUM.value)
        
        # Ensure prices are valid
        bid_price = max(0.01, bid_price)
        ask_price = max(bid_price + context.min_spread, ask_price)
        
        # Calculate sizes
        base_size = (context.bid_size + context.ask_size) / 2
        
        # Adjust sizes based on inventory
        if inventory_ratio > 0.3:  # Long inventory
            bid_size = base_size * (1 - inventory_ratio * 0.5)
            ask_size = base_size * (1 + inventory_ratio * 0.5)
            adjustments.append(QuoteAdjustmentType.INVENTORY.value)
        elif inventory_ratio < -0.3:  # Short inventory
            bid_size = base_size * (1 + abs(inventory_ratio) * 0.5)
            ask_size = base_size * (1 - abs(inventory_ratio) * 0.5)
            adjustments.append(QuoteAdjustmentType.INVENTORY.value)
        else:
            bid_size = context.bid_size
            ask_size = context.ask_size
        
        # Ensure min sizes
        bid_size = max(context.bid_size * 0.1, bid_size)
        ask_size = max(context.ask_size * 0.1, ask_size)
        
        # Calculate confidence
        confidence = 1.0 - abs(inventory_ratio) * 0.3
        confidence = max(0.1, min(1.0, confidence))
        
        # Calculate final spread
        final_spread = ask_price - bid_price
        
        return QuoteResult(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
            spread=final_spread,
            adjustments=adjustments,
            confidence=confidence,
            metadata={
                'inventory_ratio': inventory_ratio,
                'skew': skew,
                'volatility': context.volatility,
                'trend': context.market_trend
            }
        )

    async def _get_market_trend(self, symbol: str) -> str:
        """Get current market trend"""
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

    async def _get_inventory(self, symbol: str) -> Optional[Any]:
        """Get current inventory"""
        positions = await self.position_repo.get_by_symbol(symbol)
        if not positions:
            return None
        
        total_position = sum(p.size for p in positions)
        total_value = sum(p.size * p.entry_price for p in positions)
        
        class Inventory:
            def __init__(self, position, value):
                self.position = position
                self.value = value
        
        return Inventory(total_position, total_value)

    async def _place_quote_orders(
        self,
        maker_id: str,
        quote_result: QuoteResult
    ) -> None:
        """Place orders based on quote"""
        maker = self._makers[maker_id]
        
        # Get broker
        broker = self.broker_factory.get_broker_for_symbol(maker.symbol)
        if not broker:
            logger.error(f"No broker available for {maker.symbol}")
            return
        
        # Cancel existing orders
        await self._cancel_all_orders(maker_id)
        
        # Place bid order
        if quote_result.bid_size > 0:
            bid_order = {
                'symbol': maker.symbol,
                'side': 'buy',
                'size': quote_result.bid_size,
                'price': quote_result.bid_price,
                'order_type': 'limit',
                'post_only': True,
                'time_in_force': 'GTC'
            }
            result = await broker.place_order(bid_order)
            if result:
                self._order_history[maker_id].append({
                    'order_id': result.get('order_id'),
                    'type': 'bid',
                    **bid_order,
                    'timestamp': datetime.utcnow()
                })
        
        # Place ask order
        if quote_result.ask_size > 0:
            ask_order = {
                'symbol': maker.symbol,
                'side': 'sell',
                'size': quote_result.ask_size,
                'price': quote_result.ask_price,
                'order_type': 'limit',
                'post_only': True,
                'time_in_force': 'GTC'
            }
            result = await broker.place_order(ask_order)
            if result:
                self._order_history[maker_id].append({
                    'order_id': result.get('order_id'),
                    'type': 'ask',
                    **ask_order,
                    'timestamp': datetime.utcnow()
                })
        
        # Update active orders count
        maker.active_orders = 2 if (quote_result.bid_size > 0 and quote_result.ask_size > 0) else 0
        self._makers[maker_id] = maker

    # =========================================================================
    # Quote Adjustment
    # =========================================================================

    async def adjust_quote(
        self,
        maker_id: str,
        adjustments: Dict[str, Any]
    ) -> Optional[QuoteResult]:
        """
        Adjust a quote.
        
        Args:
            maker_id: Market maker ID
            adjustments: Adjustments to apply
            
        Returns:
            Optional[QuoteResult]: Adjusted quote
        """
        if maker_id not in self._makers:
            return None
        
        maker = self._makers[maker_id]
        context = self._maker_contexts[maker_id]
        
        # Apply adjustments
        if 'spread' in adjustments:
            context.base_spread = adjustments['spread']
        
        if 'bid_size' in adjustments:
            context.bid_size = adjustments['bid_size']
        
        if 'ask_size' in adjustments:
            context.ask_size = adjustments['ask_size']
        
        if 'max_position' in adjustments:
            context.max_position = adjustments['max_position']
        
        if 'inventory_target' in adjustments:
            context.inventory_target = adjustments['inventory_target']
        
        if 'skew_factor' in adjustments:
            context.skew_factor = adjustments['skew_factor']
        
        self._maker_contexts[maker_id] = context
        
        # Regenerate quote
        return await self._generate_quote(maker_id)

    # =========================================================================
    # Risk Management
    # =========================================================================

    async def check_risk_limits(self, maker_id: str) -> Dict[str, Any]:
        """
        Check risk limits for a market maker.
        
        Args:
            maker_id: Market maker ID
            
        Returns:
            Dict[str, Any]: Risk status
        """
        if maker_id not in self._makers:
            return {'error': 'Market maker not found'}
        
        maker = self._makers[maker_id]
        context = self._maker_contexts[maker_id]
        
        risk_status = {
            'overall': 'ok',
            'checks': []
        }
        
        # Check position limit
        if abs(context.inventory) > context.max_position * 0.8:
            risk_status['checks'].append({
                'type': 'position_limit',
                'status': 'warning',
                'message': f"Inventory at {abs(context.inventory)/context.max_position*100:.1f}% of limit"
            })
            risk_status['overall'] = 'warning'
        
        if abs(context.inventory) > context.max_position:
            risk_status['checks'].append({
                'type': 'position_limit',
                'status': 'critical',
                'message': f"Inventory exceeds limit: {context.inventory} > {context.max_position}"
            })
            risk_status['overall'] = 'critical'
        
        # Check spread limits
        if context.spread > context.max_spread * 1.5:
            risk_status['checks'].append({
                'type': 'spread_limit',
                'status': 'warning',
                'message': f"Spread at {context.spread/context.max_spread*100:.1f}% of max"
            })
        
        # Check volatility
        if context.volatility > 0.05:
            risk_status['checks'].append({
                'type': 'volatility',
                'status': 'warning',
                'message': f"High volatility: {context.volatility*100:.1f}%"
            })
        
        return risk_status

    # =========================================================================
    # Performance Tracking
    # =========================================================================

    async def get_performance(self, maker_id: str) -> Dict[str, Any]:
        """
        Get performance metrics for a market maker.
        
        Args:
            maker_id: Market maker ID
            
        Returns:
            Dict[str, Any]: Performance metrics
        """
        if maker_id not in self._makers:
            return {}
        
        maker = self._makers[maker_id]
        context = self._maker_contexts[maker_id]
        
        # Get trades
        trades = self._trade_history.get(maker_id, [])
        
        # Calculate metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_pnl = maker.total_pnl
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        # Calculate fill rate
        orders = self._order_history.get(maker_id, [])
        filled_orders = [o for o in orders if o.get('status') == 'filled']
        fill_rate = len(filled_orders) / len(orders) if orders else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'fill_rate': fill_rate,
            'total_orders': len(orders),
            'quote_count': maker.quote_count,
            'avg_spread': maker.current_spread,
            'max_spread': context.max_spread,
            'min_spread': context.min_spread
        }

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start monitoring all market makers"""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Market maker monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop monitoring"""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Market maker monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_running:
            try:
                for maker_id, maker in list(self._makers.items()):
                    if maker.status == MarketMakerStatus.RUNNING:
                        # Check if quote needs refresh
                        if self._should_refresh_quote(maker_id):
                            await self._generate_quote(maker_id)
                        
                        # Check risk limits
                        risk_status = await self.check_risk_limits(maker_id)
                        if risk_status.get('overall') == 'critical':
                            await self.pause_market_maker(maker_id)
                            logger.warning(f"Market maker {maker_id} paused due to risk limits")
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    def _should_refresh_quote(self, maker_id: str) -> bool:
        """Check if quote should be refreshed"""
        if maker_id not in self._makers:
            return False
        
        maker = self._makers[maker_id]
        
        # Check if quote is expired
        if maker_id in self._active_quotes:
            quote = self._active_quotes[maker_id]
            if datetime.utcnow() > quote.expires_at:
                return True
        
        # Refresh every 5 seconds
        if (datetime.utcnow() - maker.last_quote).seconds >= 5:
            return True
        
        return False

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the market maker"""
        await self.stop_monitoring()
        
        # Stop all market makers
        for maker_id in list(self._makers.keys()):
            await self.stop_market_maker(maker_id)
        
        self._makers.clear()
        self._maker_contexts.clear()
        self._active_quotes.clear()
        self._order_history.clear()
        self._trade_history.clear()
        
        logger.info("MarketMaker closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/market-making", tags=["Market Making"])


async def get_market_maker() -> MarketMaker:
    """Dependency to get MarketMaker instance"""
    return MarketMaker()


@router.post("/create", response_model=MarketMakerResponse)
async def create_market_maker(
    request: MarketMakerRequest,
    maker: MarketMaker = Depends(get_market_maker)
):
    """Create a new market maker"""
    return await maker.create_market_maker(request)


@router.get("/{maker_id}")
async def get_market_maker(
    maker_id: str,
    maker: MarketMaker = Depends(get_market_maker)
):
    """Get market maker by ID"""
    if maker_id not in maker._makers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market maker {maker_id} not found"
        )
    return maker._makers[maker_id]


@router.get("/")
async def get_all_market_makers(
    maker: MarketMaker = Depends(get_market_maker)
):
    """Get all market makers"""
    return list(maker._makers.values())


@router.post("/{maker_id}/stop")
async def stop_market_maker(
    maker_id: str,
    maker: MarketMaker = Depends(get_market_maker)
):
    """Stop a market maker"""
    success = await maker.stop_market_maker(maker_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market maker {maker_id} not found"
        )
    return {"success": True}


@router.post("/{maker_id}/pause")
async def pause_market_maker(
    maker_id: str,
    maker: MarketMaker = Depends(get_market_maker)
):
    """Pause a market maker"""
    success = await maker.pause_market_maker(maker_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market maker {maker_id} not found"
        )
    return {"success": True}


@router.post("/{maker_id}/resume")
async def resume_market_maker(
    maker_id: str,
    maker: MarketMaker = Depends(get_market_maker)
):
    """Resume a market maker"""
    success = await maker.resume_market_maker(maker_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market maker {maker_id} not found"
        )
    return {"success": True}


@router.put("/{maker_id}")
async def update_market_maker(
    maker_id: str,
    updates: Dict[str, Any] = Body(..., embed=True),
    maker: MarketMaker = Depends(get_market_maker)
):
    """Update market maker parameters"""
    result = await maker.update_market_maker(maker_id, updates)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market maker {maker_id} not found"
        )
    return result


@router.post("/{maker_id}/quote")
async def generate_quote(
    maker_id: str,
    request: Optional[QuoteRequest] = None,
    maker: MarketMaker = Depends(get_market_maker)
):
    """Generate a quote"""
    quote = await maker.generate_quote(maker_id)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market maker {maker_id} not found"
        )
    return quote


@router.post("/{maker_id}/adjust")
async def adjust_quote(
    maker_id: str,
    adjustments: Dict[str, Any] = Body(..., embed=True),
    maker: MarketMaker = Depends(get_market_maker)
):
    """Adjust a quote"""
    result = await maker.adjust_quote(maker_id, adjustments)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market maker {maker_id} not found"
        )
    return result


@router.get("/{maker_id}/risk")
async def check_risk_limits(
    maker_id: str,
    maker: MarketMaker = Depends(get_market_maker)
):
    """Check risk limits"""
    return await maker.check_risk_limits(maker_id)


@router.get("/{maker_id}/performance")
async def get_performance(
    maker_id: str,
    maker: MarketMaker = Depends(get_market_maker)
):
    """Get performance metrics"""
    return await maker.get_performance(maker_id)


@router.post("/monitor/start")
async def start_monitoring(
    maker: MarketMaker = Depends(get_market_maker)
):
    """Start market maker monitoring"""
    await maker.start_monitoring()
    return {"status": "started"}


@router.post("/monitor/stop")
async def stop_monitoring(
    maker: MarketMaker = Depends(get_market_maker)
):
    """Stop market maker monitoring"""
    await maker.stop_monitoring()
    return {"status": "stopped"}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'MarketMaker',
    'MarketMakerStatus',
    'QuoteAdjustmentType',
    'MarketMakerRequest',
    'MarketMakerResponse',
    'QuoteRequest',
    'MarketMakerContext',
    'QuoteResult',
    'router'
]
