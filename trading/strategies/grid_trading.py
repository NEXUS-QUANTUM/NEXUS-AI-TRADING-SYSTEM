# trading/strategies/grid_trading.py
"""
NEXUS AI TRADING SYSTEM - Grid Trading Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements grid trading strategies including:
- Fixed grid trading
- Dynamic grid trading
- Geometric grid
- Fibonacci grid
- Adaptive grid with volatility adjustment

Grid trading involves placing buy and sell orders at predetermined
price levels to profit from market oscillations.
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from collections import deque

import numpy as np

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType, TimeInForce
from shared.types.trading import Order, Position, Trade, MarketData
from .base import BaseStrategy, StrategyConfig, Signal, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class GridType(str, Enum):
    """Types of grid strategies"""
    FIXED = "fixed"              # Fixed price intervals
    GEOMETRIC = "geometric"      # Geometric progression (percentage-based)
    FIBONACCI = "fibonacci"      # Fibonacci-based levels
    ADAPTIVE = "adaptive"        # Adapts to market volatility
    DYNAMIC = "dynamic"          # Dynamically adjusts based on price


class GridOrderStatus(str, Enum):
    """Status of a grid order"""
    PENDING = "pending"
    PLACED = "placed"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partially_filled"


@dataclass
class GridLevel:
    """A single grid level"""
    level_id: str
    price: float
    type: str  # "buy" or "sell"
    order_id: Optional[str] = None
    status: GridOrderStatus = GridOrderStatus.PENDING
    quantity: float = 0.0
    filled_quantity: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GridConfig:
    """Configuration for grid strategy"""
    # Grid parameters
    grid_type: GridType = GridType.FIXED
    num_levels: int = 10
    grid_spacing: float = 1.0  # Percentage or absolute
    grid_range: float = 10.0   # Percentage from center
    
    # Order parameters
    order_size: float = 100.0
    min_order_size: float = 10.0
    max_order_size: float = 10000.0
    order_type: OrderType = OrderType.LIMIT
    time_in_force: TimeInForce = TimeInForce.GTC
    
    # Risk management
    max_exposure: float = 100000.0
    max_positions: int = 20
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10
    
    # Adaptivity
    adapt_to_volatility: bool = True
    volatility_lookback: int = 20
    volatility_multiplier: float = 2.0
    min_grid_spacing: float = 0.1
    max_grid_spacing: float = 5.0
    
    # Grid management
    rebalance_interval: int = 60  # seconds
    auto_rebalance: bool = True
    remove_filled_levels: bool = True
    max_active_levels: int = 50
    
    # Entry/Exit
    entry_at_center: bool = True
    exit_at_boundary: bool = True
    center_price: Optional[float] = None


@dataclass
class GridState:
    """Current state of the grid"""
    symbol: str
    grid_type: GridType
    center_price: float
    upper_bound: float
    lower_bound: float
    levels: List[GridLevel]
    active_orders: int
    filled_orders: int
    total_bought: float = 0.0
    total_sold: float = 0.0
    net_position: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_rebalance: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# GRID TRADING STRATEGY
# ============================================================================

class GridTradingStrategy(BaseStrategy):
    """
    Grid trading strategy that places buy/sell orders at predetermined price levels.
    
    The strategy creates a grid of buy and sell orders around a center price.
    When price moves, orders are filled and the grid rebalances to maintain
    consistent exposure.
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        grid_config: Optional[GridConfig] = None,
    ):
        """
        Initialize the grid strategy.
        
        Args:
            config: Strategy configuration
            grid_config: Grid-specific configuration
        """
        super().__init__(config)
        self.grid_config = grid_config or GridConfig()
        
        # Grid state
        self._grid_state: Optional[GridState] = None
        self._level_counter = 0
        
        # Order tracking
        self._placed_orders: Dict[str, Order] = {}
        self._filled_levels: List[GridLevel] = []
        
        # Price history for volatility
        self._price_history: deque = deque(maxlen=100)
        self._volatility: float = 0.0
        
        # Performance tracking
        self._grid_stats = {
            "total_levels_created": 0,
            "total_levels_filled": 0,
            "total_orders_placed": 0,
            "total_orders_filled": 0,
            "rebalance_count": 0,
            "avg_grid_spacing": 0.0,
            "current_grid_width": 0.0,
            "filled_buy_levels": 0,
            "filled_sell_levels": 0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Rebalance task
        self._rebalance_task: Optional[asyncio.Task] = None
        self._running = False
        
        self.logger = logger
    
    # ========================================================================
    # GRID INITIALIZATION
    # ========================================================================
    
    def initialize_grid(
        self,
        symbol: str,
        center_price: float,
        current_price: Optional[float] = None,
    ) -> GridState:
        """
        Initialize a new grid.
        
        Args:
            symbol: Trading symbol
            center_price: Center price for the grid
            current_price: Current market price
            
        Returns:
            GridState: Initialized grid state
        """
        price = current_price or center_price
        
        # Determine grid parameters
        grid_type = self.grid_config.grid_type
        num_levels = self.grid_config.num_levels
        grid_range = self.grid_config.grid_range / 100  # Convert to decimal
        
        # Calculate bounds
        upper_bound = center_price * (1 + grid_range)
        lower_bound = center_price * (1 - grid_range)
        
        # Generate levels
        levels = self._generate_levels(
            symbol=symbol,
            center_price=center_price,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            num_levels=num_levels,
            grid_type=grid_type,
        )
        
        # Create grid state
        state = GridState(
            symbol=symbol,
            grid_type=grid_type,
            center_price=center_price,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            levels=levels,
            active_orders=0,
            filled_orders=0,
            created_at=datetime.utcnow(),
            last_rebalance=datetime.utcnow(),
        )
        
        self._grid_state = state
        self._grid_stats["total_levels_created"] += len(levels)
        self._grid_stats["current_grid_width"] = upper_bound - lower_bound
        
        self.logger.info(
            f"Grid initialized: {symbol} @ {center_price:.2f} "
            f"[{lower_bound:.2f} - {upper_bound:.2f}] "
            f"({len(levels)} levels)"
        )
        
        return state
    
    def _generate_levels(
        self,
        symbol: str,
        center_price: float,
        lower_bound: float,
        upper_bound: float,
        num_levels: int,
        grid_type: GridType,
    ) -> List[GridLevel]:
        """
        Generate grid levels based on the grid type.
        
        Args:
            symbol: Trading symbol
            center_price: Center price
            lower_bound: Lower bound
            upper_bound: Upper bound
            num_levels: Number of levels
            grid_type: Grid type
            
        Returns:
            List[GridLevel]: Generated levels
        """
        levels = []
        
        if grid_type == GridType.FIXED:
            levels = self._generate_fixed_levels(symbol, lower_bound, upper_bound, num_levels)
        
        elif grid_type == GridType.GEOMETRIC:
            levels = self._generate_geometric_levels(symbol, center_price, lower_bound, upper_bound, num_levels)
        
        elif grid_type == GridType.FIBONACCI:
            levels = self._generate_fibonacci_levels(symbol, center_price, lower_bound, upper_bound, num_levels)
        
        elif grid_type in (GridType.ADAPTIVE, GridType.DYNAMIC):
            # Start with fixed, will adapt later
            levels = self._generate_fixed_levels(symbol, lower_bound, upper_bound, num_levels)
        
        else:
            # Default to fixed
            levels = self._generate_fixed_levels(symbol, lower_bound, upper_bound, num_levels)
        
        return levels
    
    def _generate_fixed_levels(
        self,
        symbol: str,
        lower_bound: float,
        upper_bound: float,
        num_levels: int,
    ) -> List[GridLevel]:
        """
        Generate fixed-spacing grid levels.
        
        Args:
            symbol: Trading symbol
            lower_bound: Lower bound
            upper_bound: Upper bound
            num_levels: Number of levels
            
        Returns:
            List[GridLevel]: Generated levels
        """
        levels = []
        spacing = (upper_bound - lower_bound) / (num_levels + 1)
        
        # Buy levels (below center)
        buy_levels = num_levels // 2
        sell_levels = num_levels - buy_levels
        
        # Generate buy levels
        for i in range(buy_levels):
            price = lower_bound + spacing * (i + 1)
            level = GridLevel(
                level_id=f"{symbol}_buy_{i+1}_{int(datetime.utcnow().timestamp())}",
                price=price,
                type="buy",
                quantity=self.grid_config.order_size,
            )
            levels.append(level)
        
        # Generate sell levels
        for i in range(sell_levels):
            price = upper_bound - spacing * (i + 1)
            level = GridLevel(
                level_id=f"{symbol}_sell_{i+1}_{int(datetime.utcnow().timestamp())}",
                price=price,
                type="sell",
                quantity=self.grid_config.order_size,
            )
            levels.append(level)
        
        # Sort by price
        levels.sort(key=lambda x: x.price)
        
        return levels
    
    def _generate_geometric_levels(
        self,
        symbol: str,
        center_price: float,
        lower_bound: float,
        upper_bound: float,
        num_levels: int,
    ) -> List[GridLevel]:
        """
        Generate geometric (percentage-based) grid levels.
        
        Args:
            symbol: Trading symbol
            center_price: Center price
            lower_bound: Lower bound
            upper_bound: Upper bound
            num_levels: Number of levels
            
        Returns:
            List[GridLevel]: Generated levels
        """
        levels = []
        
        # Calculate geometric ratio
        ratio = (upper_bound / center_price) ** (2 / (num_levels + 1))
        
        # Buy levels (below center)
        buy_levels = num_levels // 2
        sell_levels = num_levels - buy_levels
        
        # Generate buy levels
        for i in range(1, buy_levels + 1):
            price = center_price / (ratio ** i)
            if price >= lower_bound:
                level = GridLevel(
                    level_id=f"{symbol}_buy_{i}_{int(datetime.utcnow().timestamp())}",
                    price=price,
                    type="buy",
                    quantity=self.grid_config.order_size * (1 - i / (num_levels + 1)),
                )
                levels.append(level)
        
        # Generate sell levels
        for i in range(1, sell_levels + 1):
            price = center_price * (ratio ** i)
            if price <= upper_bound:
                level = GridLevel(
                    level_id=f"{symbol}_sell_{i}_{int(datetime.utcnow().timestamp())}",
                    price=price,
                    type="sell",
                    quantity=self.grid_config.order_size * (1 - i / (num_levels + 1)),
                )
                levels.append(level)
        
        # Sort by price
        levels.sort(key=lambda x: x.price)
        
        return levels
    
    def _generate_fibonacci_levels(
        self,
        symbol: str,
        center_price: float,
        lower_bound: float,
        upper_bound: float,
        num_levels: int,
    ) -> List[GridLevel]:
        """
        Generate Fibonacci-based grid levels.
        
        Args:
            symbol: Trading symbol
            center_price: Center price
            lower_bound: Lower bound
            upper_bound: Upper bound
            num_levels: Number of levels
            
        Returns:
            List[GridLevel]: Generated levels
        """
        levels = []
        
        # Fibonacci ratios
        fib_ratios = [
            0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0, 2.618
        ]
        
        # Select ratios based on num_levels
        selected_ratios = fib_ratios[:num_levels]
        
        # Determine direction (buy below center, sell above)
        for i, ratio in enumerate(selected_ratios):
            if ratio <= 0.5:
                # Buy level (below center)
                price = center_price * (1 - ratio)
                if price >= lower_bound:
                    level = GridLevel(
                        level_id=f"{symbol}_buy_{i+1}_{int(datetime.utcnow().timestamp())}",
                        price=price,
                        type="buy",
                        quantity=self.grid_config.order_size * (1 - ratio),
                    )
                    levels.append(level)
            else:
                # Sell level (above center)
                price = center_price * (1 + (ratio - 0.5))
                if price <= upper_bound:
                    level = GridLevel(
                        level_id=f"{symbol}_sell_{i+1}_{int(datetime.utcnow().timestamp())}",
                        price=price,
                        type="sell",
                        quantity=self.grid_config.order_size * (ratio - 0.5),
                    )
                    levels.append(level)
        
        # Sort by price
        levels.sort(key=lambda x: x.price)
        
        return levels
    
    # ========================================================================
    # GRID MANAGEMENT
    # ========================================================================
    
    async def place_grid_orders(self) -> None:
        """
        Place all pending grid orders.
        """
        if not self._grid_state:
            self.logger.warning("Grid not initialized")
            return
        
        async with self._lock:
            for level in self._grid_state.levels:
                if level.status == GridOrderStatus.PENDING:
                    await self._place_grid_order(level)
    
    async def _place_grid_order(self, level: GridLevel) -> bool:
        """
        Place a single grid order.
        
        Args:
            level: Grid level
            
        Returns:
            bool: True if order was placed successfully
        """
        try:
            side = OrderSide.BUY if level.type == "buy" else OrderSide.SELL
            
            order = Order(
                symbol=self._grid_state.symbol,
                side=side,
                order_type=self.grid_config.order_type,
                quantity=level.quantity,
                price=level.price,
                time_in_force=self.grid_config.time_in_force,
                client_order_id=level.level_id,
                metadata={
                    "grid_level": level.level_id,
                    "grid_type": self.grid_config.grid_type.value,
                    "level_type": level.type,
                },
            )
            
            # In a real implementation, this would place the order with the broker
            # For now, we simulate order placement
            order.order_id = f"grid_{level.level_id}"
            self._placed_orders[order.order_id] = order
            
            level.order_id = order.order_id
            level.status = GridOrderStatus.PLACED
            
            self._grid_state.active_orders += 1
            self._grid_stats["total_orders_placed"] += 1
            
            self.logger.debug(
                f"Placed grid order: {side.value} {level.quantity:.4f} @ {level.price:.2f}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to place grid order: {e}")
            level.status = GridOrderStatus.CANCELLED
            return False
    
    async def cancel_grid_order(self, level: GridLevel) -> bool:
        """
        Cancel a grid order.
        
        Args:
            level: Grid level
            
        Returns:
            bool: True if order was cancelled
        """
        if level.order_id and level.order_id in self._placed_orders:
            try:
                # In a real implementation, this would cancel the order with the broker
                level.status = GridOrderStatus.CANCELLED
                self._grid_state.active_orders -= 1
                del self._placed_orders[level.order_id]
                return True
            except Exception as e:
                self.logger.error(f"Failed to cancel grid order: {e}")
                return False
        return False
    
    async def handle_order_fill(self, order: Order) -> None:
        """
        Handle a filled grid order.
        
        Args:
            order: Filled order
        """
        async with self._lock:
            # Find the corresponding grid level
            level = None
            for l in self._grid_state.levels:
                if l.order_id == order.order_id:
                    level = l
                    break
            
            if not level:
                return
            
            # Update level status
            level.status = GridOrderStatus.FILLED
            level.filled_quantity = order.filled_quantity
            level.filled_at = datetime.utcnow()
            
            self._grid_state.active_orders -= 1
            self._grid_state.filled_orders += 1
            self._grid_stats["total_levels_filled"] += 1
            self._grid_stats["total_orders_filled"] += 1
            
            # Track bought/sold
            if level.type == "buy":
                self._grid_state.total_bought += level.filled_quantity * level.price
                self._grid_stats["filled_buy_levels"] += 1
            else:
                self._grid_state.total_sold += level.filled_quantity * level.price
                self._grid_stats["filled_sell_levels"] += 1
            
            # Calculate net position
            self._grid_state.net_position = (
                self._grid_state.total_bought - self._grid_state.total_sold
            )
            
            # Add to filled levels
            self._filled_levels.append(level)
            
            # Remove from grid if configured
            if self.grid_config.remove_filled_levels:
                self._grid_state.levels.remove(level)
            
            self.logger.info(
                f"Grid order filled: {level.type.upper()} {level.quantity:.4f} @ {level.price:.2f}"
            )
            
            # Rebalance after fill
            if self.grid_config.auto_rebalance:
                await self.rebalance_grid()
    
    # ========================================================================
    # GRID REBALANCING
    # ========================================================================
    
    async def rebalance_grid(self) -> None:
        """
        Rebalance the grid.
        """
        if not self._grid_state:
            return
        
        if not self.grid_config.auto_rebalance:
            return
        
        async with self._lock:
            current_price = self._price_history[-1] if self._price_history else self._grid_state.center_price
            
            # Check if rebalance is needed
            if self._should_rebalance(current_price):
                await self._perform_rebalance(current_price)
                self._grid_state.last_rebalance = datetime.utcnow()
                self._grid_stats["rebalance_count"] += 1
    
    def _should_rebalance(self, current_price: float) -> bool:
        """
        Check if rebalance is needed.
        
        Args:
            current_price: Current market price
            
        Returns:
            bool: True if rebalance is needed
        """
        if not self._grid_state:
            return False
        
        # Check time-based rebalance
        elapsed = (datetime.utcnow() - self._grid_state.last_rebalance).total_seconds()
        if elapsed >= self.grid_config.rebalance_interval:
            return True
        
        # Check if price has moved significantly
        if self.grid_config.grid_type in (GridType.ADAPTIVE, GridType.DYNAMIC):
            price_change_pct = abs(current_price - self._grid_state.center_price) / self._grid_state.center_price
            
            # Rebalance if price moved more than 50% of grid range
            grid_range_pct = (self._grid_state.upper_bound - self._grid_state.lower_bound) / self._grid_state.center_price
            if price_change_pct > grid_range_pct * 0.25:
                return True
        
        return False
    
    async def _perform_rebalance(self, current_price: float) -> None:
        """
        Perform grid rebalancing.
        
        Args:
            current_price: Current market price
        """
        if not self._grid_state:
            return
        
        self.logger.debug(f"Rebalancing grid @ {current_price:.2f}")
        
        # Check if grid needs to be shifted
        if self.grid_config.grid_type in (GridType.ADAPTIVE, GridType.DYNAMIC):
            await self._adapt_grid(current_price)
        
        # Cancel and replace stale orders
        await self._refresh_orders()
    
    async def _adapt_grid(self, current_price: float) -> None:
        """
        Adapt grid to current market conditions.
        
        Args:
            current_price: Current market price
        """
        if not self._grid_state:
            return
        
        # Calculate volatility
        if self.grid_config.adapt_to_volatility:
            self._volatility = self._calculate_volatility()
        
        # Check if grid needs to be shifted
        price_shift = current_price - self._grid_state.center_price
        shift_pct = abs(price_shift) / self._grid_state.center_price
        
        if shift_pct > 0.05:  # 5% shift triggers grid adjustment
            # Shift grid center
            new_center = current_price
            old_center = self._grid_state.center_price
            
            # Shift levels
            for level in self._grid_state.levels:
                # Cancel existing orders
                if level.status == GridOrderStatus.PLACED:
                    await self.cancel_grid_order(level)
                
                # Shift price
                level.price *= (new_center / old_center)
                level.status = GridOrderStatus.PENDING
            
            # Update grid state
            self._grid_state.center_price = new_center
            grid_range = (self._grid_state.upper_bound - self._grid_state.lower_bound) / old_center
            self._grid_state.upper_bound = new_center * (1 + grid_range / 2)
            self._grid_state.lower_bound = new_center * (1 - grid_range / 2)
            
            self.logger.info(
                f"Grid shifted to new center: {new_center:.2f} "
                f"(old: {old_center:.2f})"
            )
        
        # Adjust grid spacing based on volatility
        if self.grid_config.adapt_to_volatility and self._volatility > 0:
            new_spacing = self._calculate_adaptive_spacing()
            self._adjust_grid_spacing(new_spacing)
    
    def _calculate_volatility(self) -> float:
        """
        Calculate market volatility from price history.
        
        Returns:
            float: Volatility (standard deviation of returns)
        """
        if len(self._price_history) < self.grid_config.volatility_lookback:
            return 0.0
        
        prices = list(self._price_history)[-self.grid_config.volatility_lookback:]
        
        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        if not returns:
            return 0.0
        
        # Calculate standard deviation
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return math.sqrt(variance)
    
    def _calculate_adaptive_spacing(self) -> float:
        """
        Calculate adaptive grid spacing based on volatility.
        
        Returns:
            float: Adaptive grid spacing percentage
        """
        base_spacing = self.grid_config.grid_spacing
        volatility = self._volatility * 100
        
        # Adjust spacing based on volatility
        if volatility > 0:
            adaptive_spacing = base_spacing * (1 + volatility * self.grid_config.volatility_multiplier)
        else:
            adaptive_spacing = base_spacing
        
        # Apply limits
        adaptive_spacing = max(adaptive_spacing, self.grid_config.min_grid_spacing)
        adaptive_spacing = min(adaptive_spacing, self.grid_config.max_grid_spacing)
        
        return adaptive_spacing
    
    def _adjust_grid_spacing(self, new_spacing: float) -> None:
        """
        Adjust grid spacing.
        
        Args:
            new_spacing: New spacing percentage
        """
        if not self._grid_state:
            return
        
        # This would regenerate levels with new spacing
        # For now, just update the config
        self.grid_config.grid_spacing = new_spacing
        self._grid_stats["avg_grid_spacing"] = new_spacing
        
        self.logger.debug(f"Grid spacing adjusted to {new_spacing:.2f}%")
    
    async def _refresh_orders(self) -> None:
        """
        Refresh grid orders.
        """
        if not self._grid_state:
            return
        
        # Cancel all placed orders
        for level in self._grid_state.levels:
            if level.status == GridOrderStatus.PLACED:
                await self.cancel_grid_order(level)
        
        # Reset pending orders
        for level in self._grid_state.levels:
            if level.status == GridOrderStatus.CANCELLED:
                level.status = GridOrderStatus.PENDING
                level.order_id = None
        
        # Place all pending orders
        await self.place_grid_orders()
    
    # ========================================================================
    # GRID MONITORING
    # ========================================================================
    
    async def monitor_grid(self) -> None:
        """
        Monitor grid performance and health.
        """
        if not self._grid_state:
            return
        
        async with self._lock:
            # Check grid health
            await self._check_grid_health()
            
            # Update metrics
            await self._update_metrics()
    
    async def _check_grid_health(self) -> None:
        """
        Check grid health and take corrective actions.
        """
        if not self._grid_state:
            return
        
        # Check if grid is stuck (no activity)
        if self._grid_state.filled_orders == 0:
            elapsed = (datetime.utcnow() - self._grid_state.created_at).total_seconds()
            if elapsed > 3600:  # 1 hour
                self.logger.warning("Grid has no fills after 1 hour")
                # Consider adjusting grid
        
        # Check exposure
        exposure = abs(self._grid_state.net_position)
        if exposure > self.grid_config.max_exposure:
            self.logger.warning(f"Exposure limit exceeded: {exposure:.2f} > {self.grid_config.max_exposure}")
            # Consider pausing or reducing grid
    
    async def _update_metrics(self) -> None:
        """
        Update grid metrics.
        """
        if not self._grid_state:
            return
        
        # Calculate unrealized P&L
        if self._price_history:
            current_price = self._price_history[-1]
            
            # Calculate P&L based on position and current price
            # Simplified calculation
            if self._grid_state.net_position > 0:  # Long position
                self._grid_state.unrealized_pnl = (
                    (current_price - self._grid_state.center_price) * 
                    abs(self._grid_state.net_position) / current_price
                )
            elif self._grid_state.net_position < 0:  # Short position
                self._grid_state.unrealized_pnl = (
                    (self._grid_state.center_price - current_price) * 
                    abs(self._grid_state.net_position) / current_price
                )
            else:
                self._grid_state.unrealized_pnl = 0.0
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signal(
        self,
        market_data: List[MarketData],
    ) -> Optional[Signal]:
        """
        Generate a trading signal.
        
        Grid strategy doesn't generate traditional signals; instead it
        manages grid orders. This method is implemented to satisfy the
        BaseStrategy interface.
        
        Args:
            market_data: Market data
            
        Returns:
            Optional[Signal]: None (grid strategy is event-driven)
        """
        if not market_data:
            return None
        
        # Update price history
        current_price = market_data[-1].close
        self._price_history.append(current_price)
        
        # Initialize grid if not already
        if not self._grid_state:
            symbol = self.config.symbol or market_data[0].symbol
            center = self.grid_config.center_price or current_price
            
            self.initialize_grid(
                symbol=symbol,
                center_price=center,
                current_price=current_price,
            )
            
            # Place initial orders
            await self.place_grid_orders()
        
        # Monitor grid
        await self.monitor_grid()
        
        # No signal generated
        return None
    
    # ========================================================================
    # TRADE HANDLING
    # ========================================================================
    
    async def on_trade(self, trade: Trade) -> None:
        """
        Handle completed trade.
        
        Args:
            trade: Completed trade
        """
        await super().on_trade(trade)
        
        # Update grid P&L
        self._grid_state.realized_pnl += trade.pnl or 0.0
        
        self.logger.info(
            f"Grid trade completed: {trade.symbol} {trade.side.value} "
            f"P&L: ${trade.pnl or 0:.2f}"
        )
    
    async def on_position_update(self, position: Position) -> None:
        """
        Handle position update.
        
        Args:
            position: Updated position
        """
        await super().on_position_update(position)
        
        # Update grid position
        if self._grid_state:
            self._grid_state.net_position = position.quantity * (1 if position.side == OrderSide.BUY else -1)
    
    # ========================================================================
    # GRID STATISTICS
    # ========================================================================
    
    def get_grid_metrics(self) -> Dict[str, Any]:
        """
        Get grid performance metrics.
        
        Returns:
            Dict[str, Any]: Grid metrics
        """
        if not self._grid_state:
            return {}
        
        total_filled = self._grid_state.filled_orders
        total_placed = self._grid_stats["total_orders_placed"]
        
        return {
            "grid_state": {
                "symbol": self._grid_state.symbol,
                "grid_type": self._grid_state.grid_type.value,
                "center_price": self._grid_state.center_price,
                "upper_bound": self._grid_state.upper_bound,
                "lower_bound": self._grid_state.lower_bound,
                "active_levels": len(self._grid_state.levels),
                "active_orders": self._grid_state.active_orders,
                "filled_orders": self._grid_state.filled_orders,
                "net_position": self._grid_state.net_position,
                "unrealized_pnl": self._grid_state.unrealized_pnl,
                "realized_pnl": self._grid_state.realized_pnl,
            },
            "grid_stats": {
                "total_levels_created": self._grid_stats["total_levels_created"],
                "total_levels_filled": self._grid_stats["total_levels_filled"],
                "total_orders_placed": self._grid_stats["total_orders_placed"],
                "total_orders_filled": self._grid_stats["total_orders_filled"],
                "rebalance_count": self._grid_stats["rebalance_count"],
                "avg_grid_spacing": self._grid_stats["avg_grid_spacing"],
                "current_grid_width": self._grid_stats["current_grid_width"],
                "filled_buy_levels": self._grid_stats["filled_buy_levels"],
                "filled_sell_levels": self._grid_stats["filled_sell_levels"],
                "fill_rate": (total_filled / total_placed * 100) if total_placed > 0 else 0,
            },
            "performance": {
                "win_rate": self.metrics.win_rate,
                "net_profit": self.metrics.net_profit,
                "total_trades": self.metrics.total_trades,
                "max_drawdown": self.metrics.max_drawdown,
            },
        }
    
    # ========================================================================
    # STRATEGY LIFECYCLE
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        await super().on_start()
        self._running = True
        self.logger.info("Grid strategy started")
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        self._running = False
        
        # Cancel all grid orders
        if self._grid_state:
            for level in self._grid_state.levels:
                if level.status == GridOrderStatus.PLACED:
                    await self.cancel_grid_order(level)
        
        await super().on_stop()
        self.logger.info("Grid strategy stopped")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "GridType",
    "GridOrderStatus",
    "GridLevel",
    "GridConfig",
    "GridState",
    "GridTradingStrategy",
]
