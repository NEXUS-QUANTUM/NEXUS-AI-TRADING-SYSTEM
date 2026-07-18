"""
NEXUS AI TRADING SYSTEM - Bracket Order Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/bracket_order.py
Version: 1.0.0
Description: Advanced bracket order implementation with full API integration
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable, Tuple

from pydantic import BaseModel, Field, ConfigDict, validator

from shared.types.trading import OrderSide, OrderType, OrderStatus, TimeInForce
from shared.helpers.trading_helpers import (
    calculate_percentage_change,
    calculate_price_distance,
    round_to_tick_size,
    calculate_risk_reward,
    calculate_atr
)
from shared.constants.trading_constants import (
    MIN_ORDER_SIZE,
    DEFAULT_RISK_REWARD_RATIO,
    MAX_BRACKET_ORDERS
)
from shared.interfaces.broker import BrokerInterface
from shared.utilities.logger import get_logger

from trading.smart_orders.base_order import SmartOrder, SmartOrderConfig
from trading.smart_orders.order_manager import OrderManager

logger = get_logger(__name__)


class BracketType(str, Enum):
    """Types of bracket orders"""
    STANDARD = "standard"              # Standard bracket (entry + TP + SL)
    TRAILING = "trailing"              # Trailing bracket
    SCALING = "scaling"                # Scaling bracket
    OCO = "oco"                        # OCO bracket
    MULTI = "multi"                    # Multi-target bracket
    ADAPTIVE = "adaptive"              # Adaptive bracket
    REVERSE = "reverse"                # Reverse bracket (short entry)


class BracketStatus(str, Enum):
    """Bracket order status"""
    PENDING = "pending"                # Waiting for entry
    ACTIVE = "active"                  # Position active
    PARTIAL = "partial"                # Partially closed
    COMPLETED = "completed"            # Fully closed
    CANCELLED = "cancelled"            # Cancelled
    EXPIRED = "expired"                # Expired
    ERROR = "error"                    # Error state


class BracketLeg(BaseModel):
    """Individual bracket leg"""
    leg_type: str = Field(..., description="Leg type: entry, take_profit, stop_loss, trailing_stop")
    side: OrderSide = Field(..., description="Order side")
    order_type: OrderType = Field(..., description="Order type")
    price: Optional[float] = Field(None, description="Order price")
    stop_price: Optional[float] = Field(None, description="Stop price")
    size: float = Field(..., description="Order size")
    size_percent: Optional[float] = Field(None, description="Percentage of position")
    priority: int = Field(1, description="Priority order")
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    status: OrderStatus = Field(default=OrderStatus.PENDING)
    order_id: Optional[str] = Field(None, description="Order ID")
    filled_size: float = Field(0.0, description="Filled size")
    avg_price: float = Field(0.0, description="Average fill price")
    description: Optional[str] = Field(None, description="Leg description")


class BracketMetrics(BaseModel):
    """Metrics for bracket order performance"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    entry_price: Optional[float] = Field(None, description="Entry price")
    current_price: Optional[float] = Field(None, description="Current market price")
    
    total_size: float = Field(0.0, description="Total position size")
    filled_size: float = Field(0.0, description="Filled size")
    remaining_size: float = Field(0.0, description="Remaining size")
    
    take_profit_price: Optional[float] = Field(None, description="Take profit price")
    stop_loss_price: Optional[float] = Field(None, description="Stop loss price")
    
    realized_pnl: float = Field(0.0, description="Realized P&L")
    unrealized_pnl: float = Field(0.0, description="Unrealized P&L")
    total_pnl: float = Field(0.0, description="Total P&L")
    
    max_runup: float = Field(0.0, description="Maximum runup")
    max_drawdown: float = Field(0.0, description="Maximum drawdown")
    
    risk_reward_ratio: float = Field(0.0, description="Risk-reward ratio")
    risk_amount: float = Field(0.0, description="Risk amount")
    reward_amount: float = Field(0.0, description="Reward amount")
    
    time_to_entry: Optional[float] = Field(None, description="Time to entry in seconds")
    time_to_exit: Optional[float] = Field(None, description="Time to exit in seconds")


class BracketOrderConfig(SmartOrderConfig):
    """Configuration for bracket order"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSide = Field(..., description="Entry side")
    bracket_type: BracketType = Field(default=BracketType.STANDARD)
    
    # Entry settings
    entry_price: Optional[float] = Field(None, description="Entry price")
    entry_stop_price: Optional[float] = Field(None, description="Entry stop price")
    entry_order_type: OrderType = Field(default=OrderType.LIMIT)
    entry_size: float = Field(..., description="Entry size")
    
    # Take profit settings
    take_profit_price: Optional[float] = Field(None, description="Take profit price")
    take_profit_percent: Optional[float] = Field(None, description="Take profit percentage")
    take_profit_size_percent: float = Field(100.0, description="Percentage to take profit")
    take_profit_limit_offset: Optional[float] = Field(None, description="Limit offset for TP")
    
    # Stop loss settings
    stop_loss_price: Optional[float] = Field(None, description="Stop loss price")
    stop_loss_percent: Optional[float] = Field(None, description="Stop loss percentage")
    stop_loss_size_percent: float = Field(100.0, description="Percentage to stop loss")
    stop_loss_limit_offset: Optional[float] = Field(None, description="Limit offset for SL")
    
    # Risk management
    risk_reward_ratio: float = Field(DEFAULT_RISK_REWARD_RATIO, description="Risk-reward ratio")
    max_risk_percent: Optional[float] = Field(None, description="Maximum risk percentage")
    risk_amount: Optional[float] = Field(None, description="Fixed risk amount")
    max_loss_amount: Optional[float] = Field(None, description="Maximum loss amount")
    
    # Trailing settings
    trailing_activation_percent: Optional[float] = Field(None, description="Profit % to activate trailing")
    trailing_distance: float = Field(0.01, description="Trailing distance")
    trailing_step: float = Field(0.005, description="Trailing step")
    trail_only_in_profit: bool = Field(True, description="Only trail when in profit")
    
    # Multi-target settings
    target_levels: List[Dict[str, Any]] = Field(default_factory=list, description="Multiple target levels")
    distribution_mode: str = Field("linear", description="Distribution mode: linear, fibonacci, weighted")
    
    # Scaling settings
    scaling_activation: Optional[float] = Field(None, description="Price to activate scaling")
    scaling_step: float = Field(0.01, description="Scaling step")
    scaling_size_percent: float = Field(50.0, description="Size to scale")
    
    # Adaptive settings
    adaptive_adjustment: bool = Field(True, description="Enable adaptive adjustment")
    volatility_window: int = Field(20, description="Volatility window")
    adapt_sensitivity: float = Field(0.5, description="Adapt sensitivity")
    
    # Time settings
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    expire_after: Optional[timedelta] = Field(None, description="Expiration time")
    max_duration: Optional[float] = Field(None, description="Maximum duration in seconds")
    
    # Order settings
    max_slippage: float = Field(0.01, description="Maximum allowed slippage")
    allow_partial_fill: bool = Field(True, description="Allow partial fills")
    use_limit_orders: bool = Field(True, description="Use limit orders for exit")
    use_market_orders: bool = Field(False, description="Use market orders for exit")
    
    # Smart features
    cancel_on_position_close: bool = Field(True, description="Cancel if position closes")
    breakeven_after_profit: Optional[float] = Field(None, description="Move to breakeven after profit %")
    breakeven_buffer: float = Field(0.001, description="Breakeven buffer")
    dynamic_risk_reward: bool = Field(False, description="Dynamic risk-reward adjustment")

    @validator('entry_size')
    def validate_entry_size(cls, v):
        if v <= 0:
            raise ValueError("Entry size must be positive")
        return v

    @validator('take_profit_percent')
    def validate_take_profit_percent(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Take profit percentage must be positive")
        return v

    @validator('stop_loss_percent')
    def validate_stop_loss_percent(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Stop loss percentage must be positive")
        return v

    @validator('risk_reward_ratio')
    def validate_risk_reward(cls, v):
        if v <= 0:
            raise ValueError("Risk-reward ratio must be positive")
        return v

    @validator('trailing_distance')
    def validate_trailing(cls, v):
        if v < 0:
            raise ValueError("Trailing distance must be non-negative")
        return v


class BracketOrder(SmartOrder):
    """
    Advanced bracket order implementation with full API integration.
    
    Features:
    - Standard bracket (Entry + Take Profit + Stop Loss)
    - Trailing bracket with activation
    - Multi-target bracket with distribution
    - Scaling bracket
    - Adaptive bracket
    - OCO bracket
    - Reverse bracket
    - Dynamic risk management
    - Full broker API integration
    - Performance metrics tracking
    """

    def __init__(
        self,
        config: BracketOrderConfig,
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ):
        """
        Initialize bracket order.

        Args:
            config: Bracket order configuration
            broker: Optional broker interface
            order_manager: Optional order manager
        """
        super().__init__(config=config, broker=broker, order_manager=order_manager)
        self.config = config
        self._metrics = BracketMetrics()
        self._status = BracketStatus.PENDING
        self._current_price: Optional[float] = None
        self._legs: List[BracketLeg] = []
        self._entry_order_id: Optional[str] = None
        self._entry_filled: bool = False
        self._entry_filled_size: float = 0.0
        self._entry_avg_price: float = 0.0
        self._exit_orders_placed: bool = False
        self._trailing_active: bool = False
        self._breakeven_triggered: bool = False
        self._subscription_id: Optional[str] = None

        # Price history for adaptive features
        self._price_history: List[float] = []
        self._timestamp_history: List[datetime] = []
        self._max_history_length = 1000

        # Locks
        self._legs_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()

        logger.info(f"Initialized BracketOrder with ID: {self.id}")

    async def activate(self, price: Optional[float] = None) -> bool:
        """
        Activate the bracket order.

        Args:
            price: Optional current price

        Returns:
            bool: True if activated successfully
        """
        async with self._state_lock:
            if self._status in [BracketStatus.ACTIVE, BracketStatus.COMPLETED]:
                logger.warning(f"Bracket order {self.id} already active or completed")
                return False

            self._current_price = price or self._current_price

            # Generate legs
            self._legs = await self._generate_legs()

            if not self._legs:
                logger.error(f"No bracket legs generated for {self.id}")
                return False

            # Initialize metrics
            self._metrics.total_size = self.config.entry_size
            self._metrics.remaining_size = self.config.entry_size

            # Set initial state
            self._status = BracketStatus.ACTIVE

            # Place entry order
            if self._broker:
                await self._place_entry_order()

            logger.info(
                f"Bracket order {self.id} activated, "
                f"side: {self.config.side}, size: {self.config.entry_size}"
            )

            return True

    async def update_price(self, new_price: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Update current price and manage bracket.

        Args:
            new_price: Current market price
            timestamp: Optional timestamp

        Returns:
            bool: True if updated
        """
        async with self._state_lock:
            if self._status in [BracketStatus.COMPLETED, BracketStatus.CANCELLED]:
                return False

            self._current_price = new_price
            self._metrics.current_price = new_price

            # Update price history
            self._price_history.append(new_price)
            self._timestamp_history.append(timestamp or datetime.utcnow())
            if len(self._price_history) > self._max_history_length:
                self._price_history.pop(0)
                self._timestamp_history.pop(0)

            # Update metrics
            await self._update_metrics()

            # Check if entry is filled
            if self._entry_filled:
                # Check if we need to place exit orders
                if not self._exit_orders_placed:
                    await self._place_exit_orders()

                # Check trailing activation
                if not self._trailing_active and self.config.trailing_activation_percent:
                    profit_percent = self._calculate_profit_percent(new_price)
                    if profit_percent >= self.config.trailing_activation_percent:
                        self._trailing_active = True

                # Update trailing stops
                if self._trailing_active:
                    await self._update_trailing_stops(new_price)

                # Check breakeven trigger
                if (not self._breakeven_triggered and 
                    self.config.breakeven_after_profit is not None):
                    profit_percent = self._calculate_profit_percent(new_price)
                    if profit_percent >= self.config.breakeven_after_profit:
                        await self._trigger_breakeven()

                # Check max duration
                if self.config.max_duration:
                    elapsed = (datetime.utcnow() - self._metrics.time_to_entry).total_seconds()
                    if elapsed >= self.config.max_duration:
                        await self._close_position()

                # Check for adverse move
                if self.config.max_loss_amount:
                    if self._metrics.unrealized_pnl <= -self.config.max_loss_amount:
                        await self._close_position()

            return True

    async def check_conditions(self, price: Optional[float] = None) -> bool:
        """
        Check if bracket conditions are met.

        Args:
            price: Current price

        Returns:
            bool: True if conditions met
        """
        if self._status not in [BracketStatus.ACTIVE, BracketStatus.PARTIAL]:
            return False

        check_price = price or self._current_price
        if check_price is None:
            return False

        # Check entry conditions
        if not self._entry_filled:
            return await self._check_entry_trigger(check_price)

        # Check exit conditions
        return await self._check_exit_conditions(check_price)

    async def cancel(self) -> bool:
        """
        Cancel the bracket order.

        Returns:
            bool: True if cancelled successfully
        """
        async with self._state_lock:
            if self._status in [BracketStatus.CANCELLED, BracketStatus.COMPLETED]:
                return False

            self._status = BracketStatus.CANCELLED

            # Cancel all orders
            for leg in self._legs:
                if leg.order_id and leg.status not in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                    try:
                        await self._broker.cancel_order(leg.order_id)
                        logger.debug(f"Cancelled leg {leg.leg_type}")
                    except Exception as e:
                        logger.error(f"Failed to cancel leg {leg.leg_type}: {e}")

            logger.info(f"Bracket order {self.id} cancelled")
            return True

    async def get_metrics(self) -> BracketMetrics:
        """Get current metrics"""
        async with self._state_lock:
            return self._metrics.model_copy()

    def get_status(self) -> str:
        """Get current status"""
        return self._status.value

    def get_legs(self) -> List[BracketLeg]:
        """Get bracket legs"""
        return self._legs

    def get_entry_price(self) -> Optional[float]:
        """Get entry price"""
        return self._metrics.entry_price

    def get_take_profit_price(self) -> Optional[float]:
        """Get take profit price"""
        return self._metrics.take_profit_price

    def get_stop_loss_price(self) -> Optional[float]:
        """Get stop loss price"""
        return self._metrics.stop_loss_price

    def get_pnl(self) -> float:
        """Get total P&L"""
        return self._metrics.total_pnl

    async def _generate_legs(self) -> List[BracketLeg]:
        """Generate bracket legs"""
        legs = []

        if self.config.bracket_type == BracketType.STANDARD:
            legs = await self._generate_standard_legs()

        elif self.config.bracket_type == BracketType.TRAILING:
            legs = await self._generate_trailing_legs()

        elif self.config.bracket_type == BracketType.SCALING:
            legs = await self._generate_scaling_legs()

        elif self.config.bracket_type == BracketType.OCO:
            legs = await self._generate_oco_legs()

        elif self.config.bracket_type == BracketType.MULTI:
            legs = await self._generate_multi_legs()

        elif self.config.bracket_type == BracketType.ADAPTIVE:
            legs = await self._generate_adaptive_legs()

        elif self.config.bracket_type == BracketType.REVERSE:
            legs = await self._generate_reverse_legs()

        else:
            legs = await self._generate_standard_legs()

        return legs

    async def _generate_standard_legs(self) -> List[BracketLeg]:
        """Generate standard bracket legs"""
        legs = []

        # Entry leg
        entry_side = self.config.side
        entry_price = self.config.entry_price or self._current_price

        legs.append(BracketLeg(
            leg_type="entry",
            side=entry_side,
            order_type=self.config.entry_order_type,
            price=entry_price,
            stop_price=self.config.entry_stop_price,
            size=self.config.entry_size,
            priority=1,
            time_in_force=self.config.time_in_force,
            description="Entry order"
        ))

        # Take profit leg
        tp_price = self._calculate_take_profit_price(entry_price)
        tp_side = OrderSide.SELL if entry_side == OrderSide.BUY else OrderSide.BUY

        legs.append(BracketLeg(
            leg_type="take_profit",
            side=tp_side,
            order_type=OrderType.LIMIT,
            price=tp_price,
            size=self.config.entry_size * (self.config.take_profit_size_percent / 100),
            priority=2,
            time_in_force=self.config.time_in_force,
            description="Take profit"
        ))

        # Stop loss leg
        sl_price = self._calculate_stop_loss_price(entry_price)
        sl_side = OrderSide.SELL if entry_side == OrderSide.BUY else OrderSide.BUY

        legs.append(BracketLeg(
            leg_type="stop_loss",
            side=sl_side,
            order_type=OrderType.STOP,
            stop_price=sl_price,
            size=self.config.entry_size * (self.config.stop_loss_size_percent / 100),
            priority=3,
            time_in_force=self.config.time_in_force,
            description="Stop loss"
        ))

        # Set metrics
        self._metrics.take_profit_price = tp_price
        self._metrics.stop_loss_price = sl_price

        return legs

    async def _generate_trailing_legs(self) -> List[BracketLeg]:
        """Generate trailing bracket legs"""
        legs = await self._generate_standard_legs()

        # Add trailing stop leg
        entry_side = self.config.side
        entry_price = self.config.entry_price or self._current_price

        trailing_side = OrderSide.SELL if entry_side == OrderSide.BUY else OrderSide.BUY
        trailing_price = self._calculate_trailing_stop_price(entry_price)

        legs.append(BracketLeg(
            leg_type="trailing_stop",
            side=trailing_side,
            order_type=OrderType.STOP,
            stop_price=trailing_price,
            size=self.config.entry_size * 0.5,
            priority=4,
            time_in_force=self.config.time_in_force,
            description="Trailing stop loss"
        ))

        return legs

    async def _generate_scaling_legs(self) -> List[BracketLeg]:
        """Generate scaling bracket legs"""
        legs = []
        entry_side = self.config.side
        entry_price = self.config.entry_price or self._current_price
        num_levels = 3

        # Entry legs at different levels
        for i in range(num_levels):
            if entry_side == OrderSide.BUY:
                price = entry_price * (1 - (i + 1) * self.config.scaling_step)
            else:
                price = entry_price * (1 + (i + 1) * self.config.scaling_step)

            legs.append(BracketLeg(
                leg_type="entry",
                side=entry_side,
                order_type=OrderType.LIMIT,
                price=price,
                size=self.config.entry_size / num_levels,
                priority=i + 1,
                time_in_force=self.config.time_in_force,
                description=f"Scaling entry {i + 1}"
            ))

        # Take profit and stop loss for each entry
        for i in range(num_levels):
            entry = legs[i]
            tp_price = self._calculate_take_profit_price(entry.price)
            sl_price = self._calculate_stop_loss_price(entry.price)

            tp_side = OrderSide.SELL if entry_side == OrderSide.BUY else OrderSide.BUY

            legs.append(BracketLeg(
                leg_type="take_profit",
                side=tp_side,
                order_type=OrderType.LIMIT,
                price=tp_price,
                size=entry.size * 0.5,
                priority=num_levels + i * 2 + 1,
                time_in_force=self.config.time_in_force,
                description=f"TP for level {i + 1}"
            ))

            legs.append(BracketLeg(
                leg_type="stop_loss",
                side=tp_side,
                order_type=OrderType.STOP,
                stop_price=sl_price,
                size=entry.size * 0.5,
                priority=num_levels + i * 2 + 2,
                time_in_force=self.config.time_in_force,
                description=f"SL for level {i + 1}"
            ))

        return legs

    async def _generate_oco_legs(self) -> List[BracketLeg]:
        """Generate OCO bracket legs"""
        legs = []
        entry_side = self.config.side
        entry_price = self.config.entry_price or self._current_price

        # Entry leg
        legs.append(BracketLeg(
            leg_type="entry",
            side=entry_side,
            order_type=self.config.entry_order_type,
            price=entry_price,
            size=self.config.entry_size,
            priority=1,
            time_in_force=self.config.time_in_force,
            description="Entry order"
        ))

        # OCO: Take profit OR Stop loss (one cancels other)
        tp_price = self._calculate_take_profit_price(entry_price)
        sl_price = self._calculate_stop_loss_price(entry_price)
        exit_side = OrderSide.SELL if entry_side == OrderSide.BUY else OrderSide.BUY

        legs.append(BracketLeg(
            leg_type="take_profit",
            side=exit_side,
            order_type=OrderType.LIMIT,
            price=tp_price,
            size=self.config.entry_size,
            priority=2,
            time_in_force=self.config.time_in_force,
            description="Take profit (OCO)"
        ))

        legs.append(BracketLeg(
            leg_type="stop_loss",
            side=exit_side,
            order_type=OrderType.STOP,
            stop_price=sl_price,
            size=self.config.entry_size,
            priority=3,
            time_in_force=self.config.time_in_force,
            description="Stop loss (OCO)"
        ))

        return legs

    async def _generate_multi_legs(self) -> List[BracketLeg]:
        """Generate multi-target bracket legs"""
        legs = []
        entry_side = self.config.side
        entry_price = self.config.entry_price or self._current_price

        # Entry leg
        legs.append(BracketLeg(
            leg_type="entry",
            side=entry_side,
            order_type=self.config.entry_order_type,
            price=entry_price,
            size=self.config.entry_size,
            priority=1,
            time_in_force=self.config.time_in_force,
            description="Entry order"
        ))

        # Multiple take profit levels
        if self.config.target_levels:
            targets = self.config.target_levels
        else:
            # Generate default targets
            targets = [
                {'percent': 1.0, 'size_percent': 25},
                {'percent': 2.0, 'size_percent': 25},
                {'percent': 3.0, 'size_percent': 25},
                {'percent': 5.0, 'size_percent': 25}
            ]

        exit_side = OrderSide.SELL if entry_side == OrderSide.BUY else OrderSide.BUY

        for i, target in enumerate(targets):
            if entry_side == OrderSide.BUY:
                price = entry_price * (1 + target.get('percent', 1.0) / 100)
            else:
                price = entry_price * (1 - target.get('percent', 1.0) / 100)

            legs.append(BracketLeg(
                leg_type="take_profit",
                side=exit_side,
                order_type=OrderType.LIMIT,
                price=price,
                size=self.config.entry_size * (target.get('size_percent', 25) / 100),
                priority=i + 2,
                time_in_force=self.config.time_in_force,
                description=f"TP {i + 1}: {target.get('percent', 1.0)}%"
            ))

        # Stop loss
        sl_price = self._calculate_stop_loss_price(entry_price)
        legs.append(BracketLeg(
            leg_type="stop_loss",
            side=exit_side,
            order_type=OrderType.STOP,
            stop_price=sl_price,
            size=self.config.entry_size * 0.2,
            priority=len(targets) + 2,
            time_in_force=self.config.time_in_force,
            description="Stop loss"
        ))

        return legs

    async def _generate_adaptive_legs(self) -> List[BracketLeg]:
        """Generate adaptive bracket legs"""
        # Get market conditions
        volatility = await self._calculate_volatility()
        spread = await self._get_current_spread()

        # Adjust risk parameters based on volatility
        if volatility > 0.02:
            # High volatility: wider stops, larger targets
            risk_multiplier = 1.5
            reward_multiplier = 2.0
        elif volatility < 0.005:
            # Low volatility: tighter stops, smaller targets
            risk_multiplier = 0.7
            reward_multiplier = 0.8
        else:
            # Normal volatility
            risk_multiplier = 1.0
            reward_multiplier = 1.0

        # Create adaptive config
        adaptive_config = self.config.copy()
        if adaptive_config.stop_loss_percent:
            adaptive_config.stop_loss_percent *= risk_multiplier
        if adaptive_config.take_profit_percent:
            adaptive_config.take_profit_percent *= reward_multiplier

        # Use standard legs with adjusted parameters
        return await self._generate_standard_legs()

    async def _generate_reverse_legs(self) -> List[BracketLeg]:
        """Generate reverse bracket legs"""
        legs = []

        # Reverse entry (opposite side)
        reverse_side = OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY
        entry_price = self.config.entry_price or self._current_price

        legs.append(BracketLeg(
            leg_type="entry",
            side=reverse_side,
            order_type=self.config.entry_order_type,
            price=entry_price,
            size=self.config.entry_size,
            priority=1,
            time_in_force=self.config.time_in_force,
            description="Reverse entry"
        ))

        # Take profit (original side)
        tp_price = self._calculate_take_profit_price(entry_price, reverse=True)
        legs.append(BracketLeg(
            leg_type="take_profit",
            side=self.config.side,
            order_type=OrderType.LIMIT,
            price=tp_price,
            size=self.config.entry_size,
            priority=2,
            time_in_force=self.config.time_in_force,
            description="Reverse take profit"
        ))

        # Stop loss (original side)
        sl_price = self._calculate_stop_loss_price(entry_price, reverse=True)
        legs.append(BracketLeg(
            leg_type="stop_loss",
            side=self.config.side,
            order_type=OrderType.STOP,
            stop_price=sl_price,
            size=self.config.entry_size,
            priority=3,
            time_in_force=self.config.time_in_force,
            description="Reverse stop loss"
        ))

        return legs

    def _calculate_take_profit_price(self, entry_price: float, reverse: bool = False) -> float:
        """Calculate take profit price"""
        if self.config.take_profit_price:
            return self.config.take_profit_price

        side = self.config.side
        if reverse:
            side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY

        if self.config.take_profit_percent:
            if side == OrderSide.BUY:
                return entry_price * (1 + self.config.take_profit_percent / 100)
            else:
                return entry_price * (1 - self.config.take_profit_percent / 100)

        # Calculate based on risk-reward ratio
        sl_price = self._calculate_stop_loss_price(entry_price, reverse)
        if sl_price and self.config.risk_reward_ratio:
            risk = abs(entry_price - sl_price)
            reward = risk * self.config.risk_reward_ratio
            if side == OrderSide.BUY:
                return entry_price + reward
            else:
                return entry_price - reward

        # Default: 2% move
        if side == OrderSide.BUY:
            return entry_price * 1.02
        else:
            return entry_price * 0.98

    def _calculate_stop_loss_price(self, entry_price: float, reverse: bool = False) -> float:
        """Calculate stop loss price"""
        if self.config.stop_loss_price:
            return self.config.stop_loss_price

        side = self.config.side
        if reverse:
            side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY

        if self.config.stop_loss_percent:
            if side == OrderSide.BUY:
                return entry_price * (1 - self.config.stop_loss_percent / 100)
            else:
                return entry_price * (1 + self.config.stop_loss_percent / 100)

        # Calculate based on risk amount
        if self.config.risk_amount:
            if side == OrderSide.BUY:
                return entry_price - (self.config.risk_amount / self.config.entry_size)
            else:
                return entry_price + (self.config.risk_amount / self.config.entry_size)

        if self.config.max_risk_percent:
            if side == OrderSide.BUY:
                return entry_price * (1 - self.config.max_risk_percent / 100)
            else:
                return entry_price * (1 + self.config.max_risk_percent / 100)

        # Default: 1% stop
        if side == OrderSide.BUY:
            return entry_price * 0.99
        else:
            return entry_price * 1.01

    def _calculate_trailing_stop_price(self, current_price: float) -> float:
        """Calculate trailing stop price"""
        if self.config.side == OrderSide.BUY:
            return current_price * (1 - self.config.trailing_distance)
        else:
            return current_price * (1 + self.config.trailing_distance)

    def _calculate_profit_percent(self, current_price: float) -> float:
        """Calculate profit percentage"""
        if self._entry_avg_price == 0:
            return 0

        if self.config.side == OrderSide.BUY:
            return (current_price - self._entry_avg_price) / self._entry_avg_price * 100
        else:
            return (self._entry_avg_price - current_price) / self._entry_avg_price * 100

    async def _place_entry_order(self):
        """Place entry order"""
        entry_leg = self._get_leg_by_type("entry")
        if not entry_leg:
            return

        try:
            order_params = {
                'symbol': self.config.symbol,
                'side': entry_leg.side,
                'order_type': entry_leg.order_type,
                'quantity': entry_leg.size,
                'time_in_force': entry_leg.time_in_force,
                'client_order_id': f"{self.id}_entry"
            }

            if entry_leg.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                order_params['price'] = entry_leg.price

            if entry_leg.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                order_params['stop_price'] = entry_leg.stop_price or entry_leg.price

            result = await self._broker.place_order(**order_params)
            self._entry_order_id = result.get('order_id')
            entry_leg.order_id = self._entry_order_id
            entry_leg.status = OrderStatus.PENDING

            logger.info(f"Entry order placed: {self._entry_order_id}")

        except Exception as e:
            logger.error(f"Failed to place entry order: {e}")
            entry_leg.status = OrderStatus.REJECTED

    async def _place_exit_orders(self):
        """Place exit orders after entry is filled"""
        if self._exit_orders_placed:
            return

        async with self._legs_lock:
            for leg in self._legs:
                if leg.leg_type in ['take_profit', 'stop_loss', 'trailing_stop']:
                    try:
                        order_params = {
                            'symbol': self.config.symbol,
                            'side': leg.side,
                            'order_type': leg.order_type,
                            'quantity': leg.size,
                            'time_in_force': leg.time_in_force,
                            'client_order_id': f"{self.id}_{leg.leg_type}"
                        }

                        if leg.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                            order_params['price'] = leg.price

                        if leg.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                            order_params['stop_price'] = leg.stop_price or leg.price

                        result = await self._broker.place_order(**order_params)
                        leg.order_id = result.get('order_id')
                        leg.status = OrderStatus.PENDING

                        logger.debug(f"Exit order placed: {leg.leg_type} - {leg.order_id}")

                    except Exception as e:
                        logger.error(f"Failed to place {leg.leg_type} order: {e}")
                        leg.status = OrderStatus.REJECTED

            self._exit_orders_placed = True

    async def _check_entry_trigger(self, current_price: float) -> bool:
        """Check if entry should trigger"""
        entry_leg = self._get_leg_by_type("entry")
        if not entry_leg or entry_leg.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            return False

        # Check if entry price is reached
        if entry_leg.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            if entry_leg.side == OrderSide.BUY:
                if current_price <= entry_leg.price:
                    return await self._handle_entry_fill(entry_leg)
            else:
                if current_price >= entry_leg.price:
                    return await self._handle_entry_fill(entry_leg)

        if entry_leg.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            if entry_leg.side == OrderSide.BUY:
                if current_price >= entry_leg.stop_price:
                    return await self._handle_entry_fill(entry_leg)
            else:
                if current_price <= entry_leg.stop_price:
                    return await self._handle_entry_fill(entry_leg)

        return False

    async def _handle_entry_fill(self, entry_leg: BracketLeg) -> bool:
        """Handle entry fill"""
        try:
            # Get order status
            if entry_leg.order_id:
                status = await self._broker.get_order_status(entry_leg.order_id)
                if status.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                    filled_size = status.get('filled_quantity', entry_leg.size)
                    avg_price = status.get('price', entry_leg.price)

                    self._entry_filled = True
                    self._entry_filled_size += filled_size
                    self._entry_avg_price = (
                        (self._entry_avg_price * self._entry_filled_size + avg_price * filled_size) /
                        (self._entry_filled_size + filled_size)
                    )

                    self._metrics.entry_price = self._entry_avg_price
                    self._metrics.filled_size = self._entry_filled_size
                    self._metrics.remaining_size = self.config.entry_size - self._entry_filled_size
                    self._metrics.time_to_entry = (datetime.utcnow() - datetime.utcnow()).total_seconds()

                    entry_leg.filled_size = filled_size
                    entry_leg.avg_price = avg_price
                    entry_leg.status = OrderStatus.FILLED

                    logger.info(f"Entry filled at {avg_price}, size: {filled_size}")

                    if filled_size >= entry_leg.size * 0.99:
                        self._status = BracketStatus.ACTIVE
                        await self._place_exit_orders()
                        return True

        except Exception as e:
            logger.error(f"Error handling entry fill: {e}")

        return False

    async def _check_exit_conditions(self, current_price: float) -> bool:
        """Check if exit conditions are met"""
        if not self._entry_filled:
            return False

        # Check take profit
        tp_leg = self._get_leg_by_type("take_profit")
        if tp_leg and tp_leg.status == OrderStatus.PENDING:
            if tp_leg.side == OrderSide.BUY:
                if current_price >= tp_leg.price:
                    await self._handle_exit_fill(tp_leg)
                    return True
            else:
                if current_price <= tp_leg.price:
                    await self._handle_exit_fill(tp_leg)
                    return True

        # Check stop loss
        sl_leg = self._get_leg_by_type("stop_loss")
        if sl_leg and sl_leg.status == OrderStatus.PENDING:
            if sl_leg.side == OrderSide.BUY:
                if current_price >= sl_leg.stop_price:
                    await self._handle_exit_fill(sl_leg)
                    return True
            else:
                if current_price <= sl_leg.stop_price:
                    await self._handle_exit_fill(sl_leg)
                    return True

        # Check trailing stop
        ts_leg = self._get_leg_by_type("trailing_stop")
        if ts_leg and ts_leg.status == OrderStatus.PENDING:
            if ts_leg.side == OrderSide.BUY:
                if current_price >= ts_leg.stop_price:
                    await self._handle_exit_fill(ts_leg)
                    return True
            else:
                if current_price <= ts_leg.stop_price:
                    await self._handle_exit_fill(ts_leg)
                    return True

        return False

    async def _handle_exit_fill(self, leg: BracketLeg):
        """Handle exit fill"""
        try:
            if leg.order_id:
                status = await self._broker.get_order_status(leg.order_id)
                if status.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                    filled_size = status.get('filled_quantity', leg.size)
                    avg_price = status.get('price', leg.price or leg.stop_price)

                    leg.filled_size = filled_size
                    leg.avg_price = avg_price
                    leg.status = OrderStatus.FILLED

                    # Calculate P&L
                    if self._entry_avg_price > 0:
                        if self.config.side == OrderSide.BUY:
                            pnl = (avg_price - self._entry_avg_price) * filled_size
                        else:
                            pnl = (self._entry_avg_price - avg_price) * filled_size

                        self._metrics.realized_pnl += pnl

                    logger.info(f"Exit {leg.leg_type} filled at {avg_price}, P&L: {pnl:.2f}")

                    # Check if position is closed
                    total_filled = sum(l.filled_size for l in self._legs if l.leg_type in ['take_profit', 'stop_loss', 'trailing_stop'])
                    if total_filled >= self._entry_filled_size * 0.99:
                        self._status = BracketStatus.COMPLETED
                        self._metrics.time_to_exit = (datetime.utcnow() - datetime.utcnow()).total_seconds()
                        logger.info(f"Bracket order {self.id} completed")

        except Exception as e:
            logger.error(f"Error handling exit fill: {e}")

    async def _update_trailing_stops(self, current_price: float):
        """Update trailing stop orders"""
        ts_leg = self._get_leg_by_type("trailing_stop")
        if not ts_leg or ts_leg.status != OrderStatus.PENDING:
            return

        # Calculate new trailing stop price
        new_stop = self._calculate_trailing_stop_price(current_price)

        # Only move in favorable direction
        if self.config.side == OrderSide.BUY:
            if new_stop > ts_leg.stop_price:
                ts_leg.stop_price = new_stop
                await self._update_order(ts_leg)
        else:
            if new_stop < ts_leg.stop_price:
                ts_leg.stop_price = new_stop
                await self._update_order(ts_leg)

    async def _update_order(self, leg: BracketLeg):
        """Update an order"""
        if not leg.order_id:
            return

        try:
            update_params = {}
            if leg.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                update_params['price'] = leg.price
            if leg.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                update_params['stop_price'] = leg.stop_price

            await self._broker.update_order(leg.order_id, **update_params)
            logger.debug(f"Updated {leg.leg_type} order to price {leg.price or leg.stop_price}")

        except Exception as e:
            logger.error(f"Failed to update {leg.leg_type} order: {e}")

    async def _trigger_breakeven(self):
        """Move stop loss to breakeven"""
        if self._breakeven_triggered:
            return

        sl_leg = self._get_leg_by_type("stop_loss")
        if sl_leg and sl_leg.status == OrderStatus.PENDING:
            buffer = self.config.breakeven_buffer

            if self.config.side == OrderSide.BUY:
                sl_leg.stop_price = self._entry_avg_price + buffer
            else:
                sl_leg.stop_price = self._entry_avg_price - buffer

            await self._update_order(sl_leg)
            self._breakeven_triggered = True
            logger.info(f"Breakeven triggered at {sl_leg.stop_price}")

    async def _close_position(self):
        """Close position immediately"""
        if not self._entry_filled:
            return

        try:
            close_side = OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY
            result = await self._broker.place_order(
                symbol=self.config.symbol,
                side=close_side,
                order_type=OrderType.MARKET,
                quantity=self._entry_filled_size,
                time_in_force=TimeInForce.IOC
            )

            if result.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                self._status = BracketStatus.COMPLETED
                logger.info(f"Position closed at market price")

        except Exception as e:
            logger.error(f"Failed to close position: {e}")

    def _get_leg_by_type(self, leg_type: str) -> Optional[BracketLeg]:
        """Get leg by type"""
        for leg in self._legs:
            if leg.leg_type == leg_type:
                return leg
        return None

    async def _update_metrics(self):
        """Update metrics"""
        if self._entry_avg_price > 0 and self._current_price:
            if self.config.side == OrderSide.BUY:
                self._metrics.unrealized_pnl = (self._current_price - self._entry_avg_price) * self._entry_filled_size
            else:
                self._metrics.unrealized_pnl = (self._entry_avg_price - self._current_price) * self._entry_filled_size

        self._metrics.total_pnl = self._metrics.realized_pnl + self._metrics.unrealized_pnl

        # Update risk-reward ratio
        if self._metrics.risk_amount > 0:
            self._metrics.risk_reward_ratio = self._metrics.reward_amount / self._metrics.risk_amount

    async def _calculate_volatility(self) -> float:
        """Calculate current volatility"""
        if len(self._price_history) < self.config.volatility_window:
            return 0.01

        returns = []
        for i in range(1, self.config.volatility_window):
            if self._price_history[-i-1] != 0:
                returns.append((self._price_history[-i] - self._price_history[-i-1]) / self._price_history[-i-1])

        if not returns:
            return 0.01

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return variance ** 0.5

    async def _get_current_spread(self) -> float:
        """Get current spread"""
        # Simplified - would get from market data in production
        return 0.001

    async def register_price_feed(self, callback: Callable[[float], Awaitable[None]]):
        """Register price feed callback"""
        self._price_callback = callback

    async def start_price_monitoring(self, websocket_client: Optional[Any] = None):
        """Start price monitoring"""
        if websocket_client and not self._subscription_id:
            try:
                self._subscription_id = await websocket_client.subscribe(
                    channel='ticker',
                    symbol=self.config.symbol,
                    callback=self._handle_websocket_price
                )
                logger.info(f"Started WebSocket price monitoring for {self.config.symbol}")
            except Exception as e:
                logger.error(f"Failed to start price monitoring: {e}")

    async def _handle_websocket_price(self, data: Dict[str, Any]):
        """Handle WebSocket price updates"""
        if 'price' in data:
            await self.update_price(data['price'])

    async def stop_price_monitoring(self):
        """Stop price monitoring"""
        if self._subscription_id and self._broker:
            try:
                if hasattr(self._broker, 'unsubscribe'):
                    await self._broker.unsubscribe(self._subscription_id)
                self._subscription_id = None
                logger.info("Stopped price monitoring")
            except Exception as e:
                logger.error(f"Failed to stop price monitoring: {e}")

    async def to_dict(self) -> Dict[str, Any]:
        """Convert bracket order to dictionary"""
        return {
            'id': self.id,
            'status': self._status.value,
            'config': self.config.model_dump(),
            'metrics': self._metrics.model_dump(),
            'current_price': self._current_price,
            'legs': [leg.model_dump() for leg in self._legs],
            'entry_order_id': self._entry_order_id,
            'entry_filled': self._entry_filled,
            'entry_filled_size': self._entry_filled_size,
            'entry_avg_price': self._entry_avg_price,
            'exit_orders_placed': self._exit_orders_placed,
            'trailing_active': self._trailing_active,
            'breakeven_triggered': self._breakeven_triggered
        }

    @classmethod
    async def from_dict(
        cls,
        data: Dict[str, Any],
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ) -> 'BracketOrder':
        """Create bracket order from dictionary"""
        config = BracketOrderConfig(**data.get('config', {}))
        bracket_order = cls(config=config, broker=broker, order_manager=order_manager)

        # Restore state
        bracket_order._status = BracketStatus(data.get('status', 'pending'))
        bracket_order._current_price = data.get('current_price')
        bracket_order._entry_order_id = data.get('entry_order_id')
        bracket_order._entry_filled = data.get('entry_filled', False)
        bracket_order._entry_filled_size = data.get('entry_filled_size', 0)
        bracket_order._entry_avg_price = data.get('entry_avg_price', 0)
        bracket_order._exit_orders_placed = data.get('exit_orders_placed', False)
        bracket_order._trailing_active = data.get('trailing_active', False)
        bracket_order._breakeven_triggered = data.get('breakeven_triggered', False)

        # Restore legs
        if data.get('legs'):
            bracket_order._legs = [BracketLeg(**leg) for leg in data.get('legs')]

        # Restore metrics
        if data.get('metrics'):
            bracket_order._metrics = BracketMetrics(**data.get('metrics'))

        return bracket_order

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cancel()
        await self.stop_price_monitoring()
