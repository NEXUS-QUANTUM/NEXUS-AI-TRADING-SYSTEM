"""
NEXUS AI TRADING SYSTEM - Market Making Agent
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Market Making Agent system with:
- Bid-ask spread management
- Dynamic inventory management
- Price adjustment strategies
- Order book monitoring
- Risk management
- Performance analytics
- Multiple market making strategies
- Real-time order placement
- Order book simulation
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
from pydantic import BaseModel, Field, validator

from ai.agents.base_agent import BaseAgent, AgentHealth, AgentStatus
from ai.agents.agent_capabilities import AgentCapability
from ai.agents.agent_config import AgentConfig
from ai.agents.agent_registry import get_agent_registry
from backend.brokers.base_broker import BaseBroker
from backend.brokers.broker_factory import get_broker
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import BrokerError, OrderError, MarketDataError
from backend.models.trading import Order, OrderSide, OrderType, OrderStatus

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class MarketMakingStrategy(str, Enum):
    """Market making strategies"""
    STATIC_SPREAD = "static_spread"
    DYNAMIC_SPREAD = "dynamic_spread"
    INVENTORY_BASED = "inventory_based"
    VOLATILITY_BASED = "volatility_based"
    GRID = "grid"
    SKEWED = "skewed"
    AVERAGE_REVERSION = "average_reversion"
    AI_OPTIMIZED = "ai_optimized"


class PriceAdjustmentMethod(str, Enum):
    """Price adjustment methods"""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    SIGMOID = "sigmoid"
    ADAPTIVE = "adaptive"
    RANDOM = "random"


@dataclass
class OrderBookSnapshot:
    """Order book snapshot"""
    symbol: str
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    timestamp: datetime
    mid_price: Optional[float] = None
    spread: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    bid_depth: Optional[float] = None
    ask_depth: Optional[float] = None
    imbalance: Optional[float] = None


@dataclass
class MarketMakingPosition:
    """Market making position"""
    symbol: str
    inventory: float = 0.0
    inventory_value: float = 0.0
    average_entry: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    position_size: float = 0.0
    max_position: float = 100.0
    min_position: float = -100.0
    current_bid: Optional[float] = None
    current_ask: Optional[float] = None
    last_update: datetime = field(default_factory=datetime.utcnow)
    trades_count: int = 0


@dataclass
class MarketMakingStats:
    """Market making statistics"""
    symbol: str
    total_orders: int = 0
    filled_orders: int = 0
    canceled_orders: int = 0
    rejected_orders: int = 0
    total_volume: float = 0.0
    total_fees: float = 0.0
    gross_profit: float = 0.0
    net_profit: float = 0.0
    fill_rate: float = 0.0
    avg_spread: float = 0.0
    avg_quote_duration: float = 0.0
    max_spread: float = 0.0
    min_spread: float = 0.0
    success_rate: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0


class MarketMakingConfig(BaseModel):
    """Market making configuration"""
    enabled: bool = True
    symbol: str
    exchange: str
    spread: float = Field(default=0.001, ge=0, le=0.01)
    min_spread: float = Field(default=0.0005, ge=0, le=0.005)
    max_spread: float = Field(default=0.005, ge=0, le=0.02)
    order_size: float = Field(default=1.0, gt=0)
    min_order_size: float = Field(default=0.1, gt=0)
    max_order_size: float = Field(default=10.0, gt=0)
    inventory_target: float = Field(default=0.0)
    max_inventory: float = Field(default=100.0, gt=0)
    min_inventory: float = Field(default=-100.0, lt=0)
    inventory_skew: float = Field(default=0.0, ge=-1, le=1)
    position_skew: float = Field(default=0.0, ge=-1, le=1)
    volatility_skew: float = Field(default=0.0, ge=0, le=1)
    order_refresh_time: int = Field(default=5, gt=0)
    order_timeout: int = Field(default=30, gt=0)
    max_order_attempts: int = Field(default=3, gt=0)
    max_order_lifetime: int = Field(default=60, gt=0)
    strategy: MarketMakingStrategy = MarketMakingStrategy.DYNAMIC_SPREAD
    price_adjustment: PriceAdjustmentMethod = PriceAdjustmentMethod.ADAPTIVE
    risk_limit: float = Field(default=1000.0, gt=0)
    max_drawdown: float = Field(default=0.01, ge=0, le=1)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    order_types: List[str] = Field(default=["limit"])
    time_in_force: str = "GTC"
    use_twap: bool = False
    twap_duration: int = 60
    use_iceberg: bool = False
    iceberg_quantity: Optional[float] = None
    use_margin: bool = False
    leverage: float = Field(default=1.0, ge=0)
    quote_quantity: Optional[float] = None
    min_quote_quantity: Optional[float] = None
    max_quote_quantity: Optional[float] = None
    spread_adjustment_factor: float = Field(default=1.0, gt=0)
    volatility_window: int = Field(default=100, gt=0)
    order_book_depth: int = Field(default=10, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    metrics_collection_interval: int = Field(default=10, gt=0)
    log_level: str = "info"


# ========================================
# MARKET MAKING STRATEGIES
# ========================================

class BaseMarketMakingStrategy:
    """Base class for market making strategies"""
    
    def __init__(self, config: MarketMakingConfig):
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    async def calculate_bid_ask(
        self,
        mid_price: float,
        inventory: float,
        volatility: float,
        order_book: Optional[OrderBookSnapshot] = None
    ) -> Tuple[float, float]:
        """Calculate bid and ask prices"""
        raise NotImplementedError
    
    async def calculate_order_size(
        self,
        mid_price: float,
        inventory: float,
        volatility: float
    ) -> Tuple[float, float]:
        """Calculate bid and ask order sizes"""
        raise NotImplementedError


class StaticSpreadStrategy(BaseMarketMakingStrategy):
    """Static spread market making strategy"""
    
    async def calculate_bid_ask(
        self,
        mid_price: float,
        inventory: float,
        volatility: float,
        order_book: Optional[OrderBookSnapshot] = None
    ) -> Tuple[float, float]:
        spread = self.config.spread * self.config.spread_adjustment_factor
        bid = mid_price * (1 - spread / 2)
        ask = mid_price * (1 + spread / 2)
        return bid, ask
    
    async def calculate_order_size(
        self,
        mid_price: float,
        inventory: float,
        volatility: float
    ) -> Tuple[float, float]:
        base_size = self.config.order_size
        return base_size, base_size


class DynamicSpreadStrategy(BaseMarketMakingStrategy):
    """Dynamic spread based on volatility and inventory"""
    
    async def calculate_bid_ask(
        self,
        mid_price: float,
        inventory: float,
        volatility: float,
        order_book: Optional[OrderBookSnapshot] = None
    ) -> Tuple[float, float]:
        # Base spread
        base_spread = self.config.spread
        
        # Adjust for volatility
        vol_adjustment = volatility * self.config.volatility_skew
        spread = base_spread * (1 + vol_adjustment)
        
        # Adjust for inventory
        inventory_ratio = inventory / self.config.max_inventory
        inventory_adjustment = inventory_ratio * self.config.inventory_skew
        
        # Apply adjustments
        spread = spread * (1 + inventory_adjustment)
        spread = max(self.config.min_spread, min(self.config.max_spread, spread))
        
        # Calculate bid and ask with inventory skew
        mid_skew = mid_price * inventory_adjustment * 0.5
        bid = mid_price * (1 - spread / 2) - mid_skew
        ask = mid_price * (1 + spread / 2) - mid_skew
        
        return bid, ask
    
    async def calculate_order_size(
        self,
        mid_price: float,
        inventory: float,
        volatility: float
    ) -> Tuple[float, float]:
        base_size = self.config.order_size
        
        # Adjust size based on inventory
        inventory_ratio = inventory / self.config.max_inventory
        size_adjustment = 1 - abs(inventory_ratio) * 0.5
        
        bid_size = base_size * (1 + inventory_ratio * 0.3)
        ask_size = base_size * (1 - inventory_ratio * 0.3)
        
        bid_size = max(self.config.min_order_size, min(self.config.max_order_size, bid_size))
        ask_size = max(self.config.min_order_size, min(self.config.max_order_size, ask_size))
        
        return bid_size, ask_size


class InventoryBasedStrategy(BaseMarketMakingStrategy):
    """Inventory-based market making with aggressive skewing"""
    
    async def calculate_bid_ask(
        self,
        mid_price: float,
        inventory: float,
        volatility: float,
        order_book: Optional[OrderBookSnapshot] = None
    ) -> Tuple[float, float]:
        # Aggressive skew based on inventory
        inventory_ratio = inventory / self.config.max_inventory
        
        # Sigmoid function for smooth adjustment
        skew = 1 / (1 + math.exp(-inventory_ratio * 3)) - 0.5
        spread = self.config.spread * (1 + abs(skew) * 2)
        
        # Adjust mid price based on inventory
        mid_adjustment = mid_price * skew * 0.01
        adjusted_mid = mid_price + mid_adjustment
        
        bid = adjusted_mid * (1 - spread / 2)
        ask = adjusted_mid * (1 + spread / 2)
        
        return bid, ask
    
    async def calculate_order_size(
        self,
        mid_price: float,
        inventory: float,
        volatility: float
    ) -> Tuple[float, float]:
        inventory_ratio = inventory / self.config.max_inventory
        
        # Increase size when away from target
        size_multiplier = 1 + abs(inventory_ratio) * 1.5
        
        bid_size = self.config.order_size * size_multiplier * (1 - inventory_ratio * 0.3)
        ask_size = self.config.order_size * size_multiplier * (1 + inventory_ratio * 0.3)
        
        bid_size = max(self.config.min_order_size, min(self.config.max_order_size, bid_size))
        ask_size = max(self.config.min_order_size, min(self.config.max_order_size, ask_size))
        
        return bid_size, ask_size


class VolatilityBasedStrategy(BaseMarketMakingStrategy):
    """Volatility-aware market making"""
    
    async def calculate_bid_ask(
        self,
        mid_price: float,
        inventory: float,
        volatility: float,
        order_book: Optional[OrderBookSnapshot] = None
    ) -> Tuple[float, float]:
        # Wider spread during high volatility
        spread = self.config.spread * (1 + volatility * self.config.volatility_skew * 2)
        spread = max(self.config.min_spread, min(self.config.max_spread, spread))
        
        # Adjust for inventory
        inventory_ratio = inventory / self.config.max_inventory
        spread = spread * (1 + inventory_ratio * 0.2)
        
        bid = mid_price * (1 - spread / 2)
        ask = mid_price * (1 + spread / 2)
        
        return bid, ask
    
    async def calculate_order_size(
        self,
        mid_price: float,
        inventory: float,
        volatility: float
    ) -> Tuple[float, float]:
        # Smaller orders during high volatility
        size_factor = 1 / (1 + volatility * 2)
        base_size = self.config.order_size * size_factor
        
        # Adjust for inventory
        inventory_ratio = inventory / self.config.max_inventory
        bid_size = base_size * (1 + inventory_ratio * 0.2)
        ask_size = base_size * (1 - inventory_ratio * 0.2)
        
        bid_size = max(self.config.min_order_size, min(self.config.max_order_size, bid_size))
        ask_size = max(self.config.min_order_size, min(self.config.max_order_size, ask_size))
        
        return bid_size, ask_size


class GridStrategy(BaseMarketMakingStrategy):
    """Grid-based market making"""
    
    def __init__(self, config: MarketMakingConfig):
        super().__init__(config)
        self.grid_levels = 5
        self.grid_spacing = 0.001
    
    async def calculate_bid_ask(
        self,
        mid_price: float,
        inventory: float,
        volatility: float,
        order_book: Optional[OrderBookSnapshot] = None
    ) -> Tuple[float, float]:
        # Dynamic grid based on volatility
        grid_spacing = self.grid_spacing * (1 + volatility * 2)
        
        # Find closest grid levels
        bid = mid_price * (1 - grid_spacing * 0.5)
        ask = mid_price * (1 + grid_spacing * 0.5)
        
        return bid, ask
    
    async def calculate_order_size(
        self,
        mid_price: float,
        inventory: float,
        volatility: float
    ) -> Tuple[float, float]:
        # Distribute orders across grid levels
        base_size = self.config.order_size / self.grid_levels
        
        # Adjust for inventory
        inventory_ratio = inventory / self.config.max_inventory
        bid_size = base_size * (1 + inventory_ratio * 0.5)
        ask_size = base_size * (1 - inventory_ratio * 0.5)
        
        return bid_size, ask_size


# ========================================
# MAIN MARKET MAKING AGENT
# ========================================

class MarketMakingAgent(BaseAgent):
    """
    Market Making Agent for automated liquidity provision.
    
    Features:
    - Multiple market making strategies
    - Dynamic spread management
    - Inventory management
    - Order book monitoring
    - Real-time order placement
    - Risk management
    - Performance analytics
    - Health monitoring
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._config = MarketMakingConfig(**config)
        self._broker: Optional[BaseBroker] = None
        self._strategy: Optional[BaseMarketMakingStrategy] = None
        
        # State
        self._position: Dict[str, MarketMakingPosition] = {}
        self._stats: Dict[str, MarketMakingStats] = {}
        self._order_book: Optional[OrderBookSnapshot] = None
        self._active_orders: Dict[str, Dict] = {}
        self._last_prices: List[float] = []
        
        # Running state
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_orders_placed": 0,
            "total_orders_filled": 0,
            "total_orders_canceled": 0,
            "total_volume": 0.0,
            "total_fees": 0.0,
            "gross_profit": 0.0,
            "net_profit": 0.0,
            "win_rate": 0.0,
            "fill_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "current_drawdown": 0.0,
            "avg_spread": 0.0,
            "current_spread": 0.0
        }
        
        self._initialize_strategy()
        self._initialize_broker()
        
        self.logger.info(f"MarketMakingAgent initialized for {self._config.symbol}")
    
    def _initialize_strategy(self) -> None:
        """Initialize market making strategy"""
        strategies = {
            MarketMakingStrategy.STATIC_SPREAD: StaticSpreadStrategy,
            MarketMakingStrategy.DYNAMIC_SPREAD: DynamicSpreadStrategy,
            MarketMakingStrategy.INVENTORY_BASED: InventoryBasedStrategy,
            MarketMakingStrategy.VOLATILITY_BASED: VolatilityBasedStrategy,
            MarketMakingStrategy.GRID: GridStrategy
        }
        
        strategy_class = strategies.get(self._config.strategy)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {self._config.strategy}")
        
        self._strategy = strategy_class(self._config)
        self.logger.info(f"Initialized {self._config.strategy} strategy")
    
    def _initialize_broker(self) -> None:
        """Initialize broker connection"""
        try:
            self._broker = get_broker(self._config.exchange)
            self.logger.info(f"Initialized broker for {self._config.exchange}")
        except Exception as e:
            self.logger.error(f"Failed to initialize broker: {e}")
            raise
    
    # ========================================
    # AGENT LIFECYCLE
    # ========================================
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the market making agent"""
        self.logger.info(f"Initializing MarketMakingAgent with config: {config}")
        
        # Update config
        if config:
            self._config = MarketMakingConfig(**{**self._config.dict(), **config})
        
        # Reinitialize strategy
        self._initialize_strategy()
        
        # Initialize position
        self._position[self._config.symbol] = MarketMakingPosition(
            symbol=self._config.symbol,
            max_position=self._config.max_inventory,
            min_position=self._config.min_inventory
        )
        
        # Initialize stats
        self._stats[self._config.symbol] = MarketMakingStats(
            symbol=self._config.symbol
        )
        
        # Register capabilities
        self.capabilities = [
            AgentCapability.MARKET_MAKING,
            AgentCapability.ORDER_EXECUTION,
            AgentCapability.MARKET_DATA,
            AgentCapability.RISK_MANAGEMENT
        ]
        
        self.status = AgentStatus.INITIALIZED
        self.health = AgentHealth.HEALTHY
        self.logger.info("MarketMakingAgent initialized successfully")
    
    async def start(self) -> None:
        """Start the market making agent"""
        self.logger.info("Starting MarketMakingAgent...")
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._market_making_loop()))
        self._tasks.append(asyncio.create_task(self._order_management_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        self._tasks.append(asyncio.create_task(self._metrics_loop()))
        
        self.status = AgentStatus.RUNNING
        self.health = AgentHealth.HEALTHY
        self.logger.info("MarketMakingAgent started successfully")
    
    async def stop(self) -> None:
        """Stop the market making agent"""
        self.logger.info("Stopping MarketMakingAgent...")
        self._running = False
        
        # Cancel all orders
        await self._cancel_all_orders()
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.status = AgentStatus.STOPPED
        self.logger.info("MarketMakingAgent stopped")
    
    async def pause(self) -> None:
        """Pause the market making agent"""
        self.logger.info("Pausing MarketMakingAgent...")
        self._running = False
        
        # Cancel all orders
        await self._cancel_all_orders()
        
        self.status = AgentStatus.PAUSED
        self.logger.info("MarketMakingAgent paused")
    
    async def resume(self) -> None:
        """Resume the market making agent"""
        self.logger.info("Resuming MarketMakingAgent...")
        self._running = True
        
        # Restart background tasks
        self._tasks.append(asyncio.create_task(self._market_making_loop()))
        self._tasks.append(asyncio.create_task(self._order_management_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        self._tasks.append(asyncio.create_task(self._metrics_loop()))
        
        self.status = AgentStatus.RUNNING
        self.logger.info("MarketMakingAgent resumed")
    
    async def health_check(self) -> AgentHealth:
        """Check agent health"""
        try:
            # Check if running
            if not self._running:
                return AgentHealth.DEGRADED
            
            # Check broker
            if not self._broker:
                return AgentHealth.UNHEALTHY
            
            # Check order book
            if not self._order_book:
                return AgentHealth.DEGRADED
            
            # Check position
            pos = self._position.get(self._config.symbol)
            if pos:
                # Check if position is within limits
                if abs(pos.inventory) > self._config.max_inventory * 1.5:
                    return AgentHealth.DEGRADED
            
            return AgentHealth.HEALTHY
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return AgentHealth.UNHEALTHY
    
    # ========================================
    # MAIN MARKET MAKING LOGIC
    # ========================================
    
    async def _market_making_loop(self) -> None:
        """Main market making loop"""
        while self._running:
            try:
                await self._update_order_book()
                await self._place_orders()
                await self._update_position()
                await self._update_stats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Market making loop error: {e}")
                self.health = AgentHealth.DEGRADED
            
            await asyncio.sleep(self._config.order_refresh_time)
    
    async def _update_order_book(self) -> None:
        """Update order book snapshot"""
        try:
            if not self._broker:
                return
            
            # Get order book
            order_book = await self._broker.get_order_book(
                self._config.symbol,
                limit=self._config.order_book_depth
            )
            
            if order_book:
                bids = [(b[0], b[1]) for b in order_book.get('bids', [])]
                asks = [(a[0], a[1]) for a in order_book.get('asks', [])]
                
                best_bid = bids[0][0] if bids else None
                best_ask = asks[0][0] if asks else None
                
                self._order_book = OrderBookSnapshot(
                    symbol=self._config.symbol,
                    bids=bids,
                    asks=asks,
                    timestamp=datetime.utcnow(),
                    mid_price=(best_bid + best_ask) / 2 if best_bid and best_ask else None,
                    spread=best_ask - best_bid if best_bid and best_ask else None,
                    best_bid=best_bid,
                    best_ask=best_ask,
                    bid_depth=sum(b[1] for b in bids),
                    ask_depth=sum(a[1] for a in asks),
                    imbalance=sum(b[1] for b in bids) - sum(a[1] for a in asks)
                )
                
                # Update price history
                if self._order_book.mid_price:
                    self._last_prices.append(self._order_book.mid_price)
                    if len(self._last_prices) > self._config.volatility_window:
                        self._last_prices.pop(0)
        
        except Exception as e:
            self.logger.error(f"Failed to update order book: {e}")
            raise
    
    async def _place_orders(self) -> None:
        """Place market making orders"""
        if not self._broker or not self._order_book:
            return
        
        if not self._order_book.mid_price:
            return
        
        # Get position
        pos = self._position.get(self._config.symbol)
        if not pos:
            return
        
        # Calculate volatility
        volatility = self._calculate_volatility()
        
        # Calculate bid and ask
        bid, ask = await self._strategy.calculate_bid_ask(
            self._order_book.mid_price,
            pos.inventory,
            volatility,
            self._order_book
        )
        
        # Calculate order sizes
        bid_size, ask_size = await self._strategy.calculate_order_size(
            self._order_book.mid_price,
            pos.inventory,
            volatility
        )
        
        # Apply position skew
        inventory_ratio = pos.inventory / self._config.max_inventory
        bid_size = bid_size * (1 - inventory_ratio * 0.5)
        ask_size = ask_size * (1 + inventory_ratio * 0.5)
        
        # Apply risk limits
        bid_size = self._apply_risk_limits(bid_size, 'bid')
        ask_size = self._apply_risk_limits(ask_size, 'ask')
        
        # Place orders
        await self._place_order('bid', bid, bid_size)
        await self._place_order('ask', ask, ask_size)
        
        # Update current prices
        pos.current_bid = bid
        pos.current_ask = ask
        pos.last_update = datetime.utcnow()
    
    async def _place_order(self, side: str, price: float, size: float) -> None:
        """Place a single order"""
        if size <= 0:
            return
        
        try:
            # Check if order already exists
            existing = self._get_existing_order(side)
            
            # If order exists and is different, cancel and replace
            if existing:
                if abs(existing['price'] - price) < price * 0.001 and abs(existing['size'] - size) < size * 0.01:
                    return  # Order is close enough, skip
                
                await self._cancel_order(existing['id'])
            
            # Place new order
            order = await self._broker.create_order(
                symbol=self._config.symbol,
                side=side,
                type='limit',
                price=price,
                quantity=size,
                time_in_force=self._config.time_in_force
            )
            
            if order:
                self._active_orders[order['id']] = {
                    'id': order['id'],
                    'side': side,
                    'price': price,
                    'size': size,
                    'placed_at': datetime.utcnow()
                }
                self._metrics["total_orders_placed"] += 1
                
                self.logger.debug(f"Placed {side} order: {size} @ {price}")
        
        except Exception as e:
            self.logger.error(f"Failed to place {side} order: {e}")
    
    def _get_existing_order(self, side: str) -> Optional[Dict]:
        """Get existing order for side"""
        for order_id, order in self._active_orders.items():
            if order['side'] == side:
                return order
        return None
    
    async def _cancel_order(self, order_id: str) -> None:
        """Cancel an order"""
        try:
            if self._broker:
                await self._broker.cancel_order(order_id)
            
            if order_id in self._active_orders:
                del self._active_orders[order_id]
                self._metrics["total_orders_canceled"] += 1
                
                self.logger.debug(f"Canceled order {order_id}")
        
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
    
    async def _cancel_all_orders(self) -> None:
        """Cancel all active orders"""
        for order_id in list(self._active_orders.keys()):
            await self._cancel_order(order_id)
    
    async def _order_management_loop(self) -> None:
        """Order management loop for monitoring and maintenance"""
        while self._running:
            try:
                await self._check_order_status()
                await self._cleanup_stale_orders()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Order management loop error: {e}")
            
            await asyncio.sleep(5)
    
    async def _check_order_status(self) -> None:
        """Check status of active orders"""
        if not self._broker:
            return
        
        for order_id in list(self._active_orders.keys()):
            try:
                status = await self._broker.get_order_status(order_id)
                
                if status.get('status') == OrderStatus.FILLED:
                    # Order filled
                    filled_size = status.get('executed_qty', 0)
                    avg_price = status.get('avg_price', 0)
                    
                    # Update position
                    pos = self._position.get(self._config.symbol)
                    if pos:
                        order = self._active_orders[order_id]
                        if order['side'] == 'bid':
                            pos.inventory += filled_size
                            pos.inventory_value += filled_size * avg_price
                            pos.trades_count += 1
                        else:
                            pos.inventory -= filled_size
                            pos.inventory_value -= filled_size * avg_price
                            pos.trades_count += 1
                        
                        # Update stats
                        stats = self._stats.get(self._config.symbol)
                        if stats:
                            stats.filled_orders += 1
                            stats.total_volume += filled_size
                            stats.total_trades += 1
                    
                    self._metrics["total_orders_filled"] += 1
                    
                    # Remove from active orders
                    del self._active_orders[order_id]
                    
                    self.logger.info(f"Order {order_id} filled: {filled_size} @ {avg_price}")
                
                elif status.get('status') in [OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED]:
                    # Order canceled/rejected/expired
                    if order_id in self._active_orders:
                        del self._active_orders[order_id]
                        self._metrics["total_orders_canceled"] += 1
            
            except Exception as e:
                self.logger.error(f"Failed to check order {order_id}: {e}")
    
    async def _cleanup_stale_orders(self) -> None:
        """Clean up stale orders"""
        now = datetime.utcnow()
        stale_orders = []
        
        for order_id, order in self._active_orders.items():
            age = (now - order['placed_at']).total_seconds()
            if age > self._config.max_order_lifetime:
                stale_orders.append(order_id)
        
        for order_id in stale_orders:
            await self._cancel_order(order_id)
    
    async def _update_position(self) -> None:
        """Update position information"""
        pos = self._position.get(self._config.symbol)
        if not pos or not self._order_book:
            return
        
        if self._order_book.mid_price:
            # Calculate unrealized P&L
            current_value = pos.inventory * self._order_book.mid_price
            pos.unrealized_pnl = current_value - pos.inventory_value
            
            # Update total P&L
            pos.total_pnl = pos.realized_pnl + pos.unrealized_pnl
    
    async def _update_stats(self) -> None:
        """Update market making statistics"""
        stats = self._stats.get(self._config.symbol)
        if not stats:
            return
        
        # Update fill rate
        if stats.total_orders > 0:
            stats.fill_rate = stats.filled_orders / stats.total_orders
        
        # Update win rate
        if stats.total_trades > 0:
            stats.win_rate = stats.winning_trades / stats.total_trades
        
        # Update Sharpe ratio
        if stats.total_trades > 1:
            # Simplified Sharpe calculation
            returns = [stats.gross_profit / stats.total_volume] if stats.total_volume > 0 else [0]
            if returns:
                mean_return = np.mean(returns)
                std_return = np.std(returns) if len(returns) > 1 else 0.01
                stats.sharpe_ratio = mean_return / std_return if std_return > 0 else 0
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    def _calculate_volatility(self) -> float:
        """Calculate current volatility"""
        if len(self._last_prices) < 2:
            return 0.0
        
        returns = [
            (self._last_prices[i] - self._last_prices[i-1]) / self._last_prices[i-1]
            for i in range(1, len(self._last_prices))
        ]
        
        if not returns:
            return 0.0
        
        return np.std(returns) * math.sqrt(252)  # Annualized volatility
    
    def _apply_risk_limits(self, size: float, side: str) -> float:
        """Apply risk limits to order size"""
        pos = self._position.get(self._config.symbol)
        if not pos:
            return 0.0
        
        # Check position limits
        if side == 'bid':
            if pos.inventory + size > self._config.max_inventory:
                size = max(0, self._config.max_inventory - pos.inventory)
        else:
            if pos.inventory - size < self._config.min_inventory:
                size = max(0, pos.inventory - self._config.min_inventory)
        
        # Apply order size limits
        size = max(0, min(size, self._config.max_order_size))
        size = max(self._config.min_order_size, size)
        
        return size
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_position(self) -> Dict[str, Any]:
        """Get current position"""
        pos = self._position.get(self._config.symbol)
        if not pos:
            return {}
        
        return {
            "symbol": pos.symbol,
            "inventory": pos.inventory,
            "inventory_value": pos.inventory_value,
            "unrealized_pnl": pos.unrealized_pnl,
            "realized_pnl": pos.realized_pnl,
            "total_pnl": pos.total_pnl,
            "current_bid": pos.current_bid,
            "current_ask": pos.current_ask,
            "trades_count": pos.trades_count,
            "last_update": pos.last_update.isoformat()
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get market making stats"""
        stats = self._stats.get(self._config.symbol)
        if not stats:
            return {}
        
        return {
            "symbol": stats.symbol,
            "total_orders": stats.total_orders,
            "filled_orders": stats.filled_orders,
            "canceled_orders": stats.canceled_orders,
            "rejected_orders": stats.rejected_orders,
            "total_volume": stats.total_volume,
            "total_fees": stats.total_fees,
            "gross_profit": stats.gross_profit,
            "net_profit": stats.net_profit,
            "fill_rate": stats.fill_rate,
            "avg_spread": stats.avg_spread,
            "max_spread": stats.max_spread,
            "min_spread": stats.min_spread,
            "success_rate": stats.success_rate,
            "sharpe_ratio": stats.sharpe_ratio,
            "win_rate": stats.win_rate,
            "total_trades": stats.total_trades,
            "winning_trades": stats.winning_trades,
            "losing_trades": stats.losing_trades
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        return {
            **self._metrics,
            "position": await self.get_position(),
            "stats": await self.get_stats(),
            "order_book": {
                "mid_price": self._order_book.mid_price if self._order_book else None,
                "spread": self._order_book.spread if self._order_book else None,
                "bid_depth": self._order_book.bid_depth if self._order_book else None,
                "ask_depth": self._order_book.ask_depth if self._order_book else None,
                "imbalance": self._order_book.imbalance if self._order_book else None
            } if self._order_book else {},
            "active_orders": len(self._active_orders),
            "volatility": self._calculate_volatility(),
            "running": self._running,
            "status": self.status,
            "health": self.health
        }
    
    async def get_order_book(self) -> Optional[OrderBookSnapshot]:
        """Get current order book snapshot"""
        return self._order_book
    
    async def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get active orders"""
        return list(self._active_orders.values())
    
    async def force_update(self) -> None:
        """Force an immediate update"""
        await self._update_order_book()
        await self._place_orders()
        await self._update_position()
        await self._update_stats()
    
    async def set_spread(self, spread: float) -> None:
        """Set the spread"""
        self._config.spread = max(self._config.min_spread, min(self._config.max_spread, spread))
        self.logger.info(f"Spread updated to {self._config.spread}")
    
    async def set_order_size(self, size: float) -> None:
        """Set the order size"""
        self._config.order_size = max(self._config.min_order_size, min(self._config.max_order_size, size))
        self.logger.info(f"Order size updated to {self._config.order_size}")
    
    async def set_inventory_target(self, target: float) -> None:
        """Set the inventory target"""
        self._config.inventory_target = max(self._config.min_inventory, min(self._config.max_inventory, target))
        self.logger.info(f"Inventory target updated to {self._config.inventory_target}")
    
    # ========================================
    # HEALTH MONITORING
    # ========================================
    
    async def _health_loop(self) -> None:
        """Health monitoring loop"""
        while self._running:
            try:
                self.health = await self.health_check()
                self.logger.debug(f"Health: {self.health}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
            
            await asyncio.sleep(self._config.health_check_interval)
    
    async def _metrics_loop(self) -> None:
        """Metrics collection loop"""
        while self._running:
            try:
                # Update metrics
                stats = self._stats.get(self._config.symbol)
                if stats:
                    self._metrics["fill_rate"] = stats.fill_rate
                    self._metrics["win_rate"] = stats.win_rate
                    self._metrics["sharpe_ratio"] = stats.sharpe_ratio
                    
                    if self._order_book:
                        self._metrics["current_spread"] = self._order_book.spread or 0
                
                # Save state
                await self.save_state()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics loop error: {e}")
            
            await asyncio.sleep(self._config.metrics_collection_interval)
    
    # ========================================
    # STATE PERSISTENCE
    # ========================================
    
    async def save_state(self) -> None:
        """Save agent state"""
        try:
            state = {
                "position": await self.get_position(),
                "stats": await self.get_stats(),
                "metrics": self._metrics,
                "active_orders": await self.get_active_orders()
            }
            
            key = f"market_making_state:{self.agent_id}"
            self.redis.setex(
                key,
                settings.REDIS_AGENT_TTL,
                json.dumps(state, default=str)
            )
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")


# ========================================
# DEPENDENCY INJECTION
# ========================================

def create_market_making_agent(config: Dict[str, Any]) -> MarketMakingAgent:
    """Create a market making agent instance"""
    return MarketMakingAgent(config)


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'MarketMakingAgent',
    'MarketMakingConfig',
    'MarketMakingStrategy',
    'PriceAdjustmentMethod',
    'OrderBookSnapshot',
    'MarketMakingPosition',
    'MarketMakingStats',
    'create_market_making_agent'
]
