"""
NEXUS AI TRADING SYSTEM - OCO (One-Cancels-Other) Order Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/oco_order.py
Version: 1.0.0
Description: Advanced OCO order implementation with full API integration
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable, Tuple

from pydantic import BaseModel, Field, ConfigDict, validator

from shared.types.trading import OrderSide, OrderType, OrderStatus, TimeInForce
from shared.helpers.trading_helpers import (
    calculate_percentage_change,
    calculate_price_distance,
    round_to_tick_size,
    calculate_risk_reward
)
from shared.constants.trading_constants import (
    MIN_ORDER_SIZE,
    DEFAULT_RISK_REWARD_RATIO,
    MAX_OCO_ORDERS
)
from shared.interfaces.broker import BrokerInterface
from trading.smart_orders.base_order import SmartOrder, SmartOrderConfig
from trading.smart_orders.order_manager import OrderManager

logger = logging.getLogger(__name__)


class OCOType(str, Enum):
    """Types of OCO orders"""
    STANDARD = "standard"              # Standard OCO (limit + stop)
    BRACKET = "bracket"                # Bracket order (entry + take profit + stop loss)
    OTO = "oto"                        # One-Triggers-Other
    OTOCO = "otoco"                    # One-Triggers-One-Cancels-Other
    CHAIN = "chain"                    # Chain of OCO orders
    TRAILING = "trailing"              # Trailing OCO
    SCALING = "scaling"                # Scaling OCO
    ADAPTIVE = "adaptive"              # Adaptive OCO


class OCOLegType(str, Enum):
    """Types of OCO legs"""
    ENTRY = "entry"                    # Entry order
    TAKE_PROFIT = "take_profit"        # Take profit order
    STOP_LOSS = "stop_loss"            # Stop loss order
    TRAILING_STOP = "trailing_stop"    # Trailing stop order
    SCALING = "scaling"                # Scaling order
    HEDGE = "hedge"                    # Hedge order


class OCOLeg(BaseModel):
    """Individual OCO leg configuration"""
    leg_type: OCOLegType = Field(..., description="Type of leg")
    side: OrderSide = Field(..., description="Order side")
    order_type: OrderType = Field(default=OrderType.LIMIT, description="Order type")
    price: Optional[float] = Field(None, description="Order price")
    stop_price: Optional[float] = Field(None, description="Stop price (for stop orders)")
    size: float = Field(..., description="Order size")
    size_percent: Optional[float] = Field(None, description="Percentage of total size")
    priority: int = Field(1, description="Priority order")
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    trigger_price: Optional[float] = Field(None, description="Trigger price for OTO")
    expire_at: Optional[datetime] = Field(None, description="Expiration time")
    description: Optional[str] = Field(None, description="Description of this leg")
    trailing_distance: Optional[float] = Field(None, description="Trailing distance for trailing stops")
    trail_activation: Optional[float] = Field(None, description="Activation price for trailing")

    @validator('size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Size must be positive")
        return v


class OCOConfig(SmartOrderConfig):
    """Configuration for OCO order"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    oco_type: OCOType = Field(default=OCOType.STANDARD)
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSide = Field(..., description="Primary order side")
    total_size: float = Field(..., description="Total order size")

    # Primary order
    entry_price: Optional[float] = Field(None, description="Entry price")
    entry_stop_price: Optional[float] = Field(None, description="Entry stop price")
    entry_order_type: OrderType = Field(default=OrderType.LIMIT)

    # Take profit
    take_profit_price: Optional[float] = Field(None, description="Take profit price")
    take_profit_percent: Optional[float] = Field(None, description="Take profit percentage")
    take_profit_size: Optional[float] = Field(None, description="Take profit size")
    take_profit_size_percent: float = Field(100.0, description="Percentage to take profit")

    # Stop loss
    stop_loss_price: Optional[float] = Field(None, description="Stop loss price")
    stop_loss_percent: Optional[float] = Field(None, description="Stop loss percentage")
    stop_loss_size: Optional[float] = Field(None, description="Stop loss size")
    stop_loss_size_percent: float = Field(100.0, description="Percentage to stop loss")

    # Risk management
    risk_reward_ratio: float = Field(DEFAULT_RISK_REWARD_RATIO, description="Risk-reward ratio")
    max_risk_percent: Optional[float] = Field(None, description="Maximum risk percentage")
    risk_amount: Optional[float] = Field(None, description="Fixed risk amount")

    # OTO settings
    trigger_price: Optional[float] = Field(None, description="Trigger price for OTO")
    trigger_direction: Optional[str] = Field(None, description="Trigger direction (above/below)")

    # Chain settings
    chain_orders: List[Dict[str, Any]] = Field(default_factory=list, description="Chain of orders")
    chain_condition: str = Field("all", description="Chain condition (all/any)")

    # Trailing settings
    trailing_activation: Optional[float] = Field(None, description="Activation price for trailing")
    trailing_distance: float = Field(0.01, description="Trailing distance")
    trailing_step: float = Field(0.005, description="Trailing step")

    # Scaling settings
    scaling_levels: List[Dict[str, Any]] = Field(default_factory=list, description="Scaling levels")
    scaling_mode: str = Field("linear", description="Scaling mode")

    # Order settings
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    expire_after: Optional[timedelta] = Field(None, description="Expiration time")
    max_slippage: float = Field(0.01, description="Maximum slippage")
    allow_partial_fill: bool = Field(True, description="Allow partial fills")

    # Smart features
    adaptive_adjustment: bool = Field(True, description="Enable adaptive adjustment")
    cancel_on_position_close: bool = Field(True, description="Cancel if position closes")
    dynamic_risk_reward: bool = Field(False, description="Dynamic risk-reward adjustment")

    @validator('total_size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Total size must be positive")
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


class OCOState(str, Enum):
    """States of an OCO order"""
    PENDING = "pending"                # Waiting to be placed
    ACTIVE = "active"                  # Active and monitoring
    PARTIAL = "partial"                # Partially executed
    TRIGGERED = "triggered"            # Triggered (for OTO)
    EXECUTED = "executed"              # Fully executed
    CANCELLED = "cancelled"            # Cancelled
    EXPIRED = "expired"                # Expired
    ERROR = "error"                    # Error state


class OCOExecution(BaseModel):
    """Execution result for an OCO leg"""
    leg_index: int
    leg_type: OCOLegType
    order_id: str
    executed_price: float
    executed_size: float
    status: OrderStatus
    timestamp: datetime
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class OCOMetrics(BaseModel):
    """Metrics for OCO order performance"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    entry_price: Optional[float] = Field(None, description="Entry price")
    current_price: Optional[float] = Field(None, description="Current market price")
    take_profit_price: Optional[float] = Field(None, description="Take profit price")
    stop_loss_price: Optional[float] = Field(None, description="Stop loss price")

    total_size: float = Field(0.0, description="Total size")
    executed_size: float = Field(0.0, description="Executed size")
    remaining_size: float = Field(0.0, description="Remaining size")

    realized_pnl: float = Field(0.0, description="Realized P&L")
    unrealized_pnl: float = Field(0.0, description="Unrealized P&L")
    total_pnl: float = Field(0.0, description="Total P&L")

    legs_executed: int = Field(0, description="Number of legs executed")
    total_legs: int = Field(0, description="Total number of legs")

    max_runup: float = Field(0.0, description="Maximum runup")
    max_drawdown: float = Field(0.0, description="Maximum drawdown")

    time_to_execution: Optional[float] = Field(None, description="Time to execution in seconds")
    fill_rate: float = Field(0.0, description="Fill rate percentage")


class OCOOrder(SmartOrder):
    """
    Advanced OCO (One-Cancels-Other) order implementation with full API integration.

    Supports multiple OCO types:
    - Standard OCO (Limit + Stop)
    - Bracket orders (Entry + TP + SL)
    - OTO (One-Triggers-Other)
    - OTOCO (One-Triggers-One-Cancels-Other)
    - Chain orders
    - Trailing OCO
    - Scaling OCO

    Features:
    - Multiple leg management
    - Conditional triggering
    - Dynamic adjustment
    - Risk management
    - Full broker API integration
    - Performance metrics tracking
    """

    def __init__(
        self,
        config: OCOConfig,
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ):
        """
        Initialize OCO order.

        Args:
            config: OCO configuration
            broker: Optional broker interface for execution
            order_manager: Optional order manager for coordination
        """
        super().__init__(config=config, broker=broker, order_manager=order_manager)
        self.config = config
        self._metrics = OCOMetrics()
        self._state = OCOState.PENDING
        self._current_price: Optional[float] = None
        self._legs: List[OCOLeg] = []
        self._order_ids: Dict[int, str] = {}  # leg_index -> order_id
        self._executed_legs: List[int] = []
        self._cancelled_legs: List[int] = []
        self._active_legs: List[int] = []
        self._executed_size: float = 0.0
        self._remaining_size: float = 0.0
        self._entry_price_actual: Optional[float] = None
        self._stop_triggered: bool = False
        self._profit_taken: bool = False
        self._subscription_id: Optional[str] = None
        self._triggered_legs: List[int] = []  # For OTO/OTOCO

        # Price history for adaptive adjustments
        self._price_history: List[float] = []
        self._timestamp_history: List[datetime] = []
        self._max_history_length = 1000

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(f"Initialized OCOOrder with ID: {self.id}")

    async def activate(self, price: Optional[float] = None) -> bool:
        """
        Activate the OCO order.

        Args:
            price: Optional current price

        Returns:
            bool: True if activated successfully
        """
        async with self._lock:
            if self._state in [OCOState.ACTIVE, OCOState.EXECUTED]:
                logger.warning(f"OCO order {self.id} already active or executed")
                return False

            self._current_price = price or self._current_price

            # Generate legs
            self._legs = await self._generate_legs()

            if not self._legs:
                logger.error(f"No OCO legs generated for {self.id}")
                return False

            # Calculate metrics
            self._metrics.total_legs = len(self._legs)
            self._metrics.total_size = self.config.total_size
            self._metrics.remaining_size = self.config.total_size

            # Set initial state
            self._state = OCOState.ACTIVE
            self._remaining_size = self.config.total_size

            # Submit orders
            if self._broker:
                await self._submit_orders()

            logger.info(
                f"OCO order {self.id} activated, "
                f"legs: {len(self._legs)}, size: {self.config.total_size}"
            )

            return True

    async def update_price(self, new_price: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Update current price and check conditions.

        Args:
            new_price: Current market price
            timestamp: Optional timestamp

        Returns:
            bool: True if any conditions triggered
        """
        async with self._lock:
            if self._state not in [OCOState.ACTIVE, OCOState.PARTIAL]:
                return False

            self._current_price = new_price

            # Update price history
            self._price_history.append(new_price)
            self._timestamp_history.append(timestamp or datetime.utcnow())
            if len(self._price_history) > self._max_history_length:
                self._price_history.pop(0)
                self._timestamp_history.pop(0)

            # Update metrics
            self._metrics.current_price = new_price

            # Check for OTO triggers
            if self.config.oco_type in [OCOType.OTO, OCOType.OTOCO]:
                await self._check_oto_triggers(new_price)

            # Check for entry triggers
            if self.config.oco_type == OCOType.BRACKET:
                await self._check_bracket_trigger(new_price)

            # Check for trailing updates
            if self.config.oco_type == OCOType.TRAILING:
                await self._update_trailing_orders(new_price)

            # Check for adaptive adjustments
            if self.config.adaptive_adjustment:
                await self._adjust_adaptive_orders(new_price)

            # Check for position close
            if self.config.cancel_on_position_close:
                await self._check_position_close()

            # Check for orders to execute
            triggered = await self._check_legs_trigger(new_price)

            # Update metrics
            await self._update_metrics()

            return triggered

    async def check_conditions(self, price: Optional[float] = None) -> bool:
        """
        Check if OCO conditions are met.

        Args:
            price: Current price to check

        Returns:
            bool: True if any conditions met
        """
        check_price = price or self._current_price
        if check_price is None:
            return False

        async with self._lock:
            if self._state not in [OCOState.ACTIVE, OCOState.PARTIAL]:
                return False

            return await self._check_legs_trigger(check_price)

    async def cancel(self, cancel_all: bool = True) -> bool:
        """
        Cancel the OCO order.

        Args:
            cancel_all: Cancel all legs if True

        Returns:
            bool: True if cancelled successfully
        """
        async with self._lock:
            if self._state == OCOState.CANCELLED:
                return False

            self._state = OCOState.CANCELLED

            # Cancel all orders
            for leg_index, order_id in self._order_ids.items():
                if leg_index not in self._executed_legs:
                    try:
                        await self._broker.cancel_order(order_id)
                        logger.debug(f"Cancelled order {order_id} for leg {leg_index}")
                        self._cancelled_legs.append(leg_index)
                    except Exception as e:
                        logger.error(f"Failed to cancel order {order_id}: {e}")

            self._order_ids.clear()
            self._active_legs.clear()

            logger.info(f"OCO order {self.id} cancelled")
            return True

    async def get_metrics(self) -> OCOMetrics:
        """Get current OCO metrics"""
        async with self._lock:
            return self._metrics.model_copy()

    def get_state(self) -> str:
        """Get current state"""
        return self._state.value

    def get_legs(self) -> List[OCOLeg]:
        """Get OCO legs"""
        return self._legs

    def get_executed_legs(self) -> List[int]:
        """Get executed leg indices"""
        return self._executed_legs

    def get_remaining_size(self) -> float:
        """Get remaining size"""
        return self._remaining_size

    def get_executed_size(self) -> float:
        """Get executed size"""
        return self._executed_size

    async def _generate_legs(self) -> List[OCOLeg]:
        """Generate OCO legs based on configuration"""
        legs = []

        if self.config.oco_type == OCOType.STANDARD:
            legs = await self._generate_standard_legs()

        elif self.config.oco_type == OCOType.BRACKET:
            legs = await self._generate_bracket_legs()

        elif self.config.oco_type == OCOType.OTO:
            legs = await self._generate_oto_legs()

        elif self.config.oco_type == OCOType.OTOCO:
            legs = await self._generate_otoco_legs()

        elif self.config.oco_type == OCOType.CHAIN:
            legs = await self._generate_chain_legs()

        elif self.config.oco_type == OCOType.TRAILING:
            legs = await self._generate_trailing_legs()

        elif self.config.oco_type == OCOType.SCALING:
            legs = await self._generate_scaling_legs()

        elif self.config.oco_type == OCOType.ADAPTIVE:
            legs = await self._generate_adaptive_legs()

        # Filter and validate legs
        legs = self._filter_and_validate_legs(legs)

        # Set active legs
        self._active_legs = list(range(len(legs)))

        return legs

    async def _generate_standard_legs(self) -> List[OCOLeg]:
        """Generate standard OCO legs (limit + stop)"""
        legs = []

        # Entry leg
        legs.append(OCOLeg(
            leg_type=OCOLegType.ENTRY,
            side=self.config.side,
            order_type=self.config.entry_order_type,
            price=self.config.entry_price,
            stop_price=self.config.entry_stop_price,
            size=self.config.total_size,
            priority=1,
            time_in_force=self.config.time_in_force,
            description="Entry order"
        ))

        # Take profit leg (opposite side)
        tp_price = self._calculate_take_profit_price(self.config.entry_price)
        legs.append(OCOLeg(
            leg_type=OCOLegType.TAKE_PROFIT,
            side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=tp_price,
            size=self.config.total_size * (self.config.take_profit_size_percent / 100),
            priority=2,
            time_in_force=self.config.time_in_force,
            description="Take profit order"
        ))

        # Stop loss leg (opposite side)
        sl_price = self._calculate_stop_loss_price(self.config.entry_price)
        legs.append(OCOLeg(
            leg_type=OCOLegType.STOP_LOSS,
            side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.STOP,
            stop_price=sl_price,
            size=self.config.total_size * (self.config.stop_loss_size_percent / 100),
            priority=3,
            time_in_force=self.config.time_in_force,
            description="Stop loss order"
        ))

        return legs

    async def _generate_bracket_legs(self) -> List[OCOLeg]:
        """Generate bracket order legs"""
        legs = []

        # Entry leg
        legs.append(OCOLeg(
            leg_type=OCOLegType.ENTRY,
            side=self.config.side,
            order_type=self.config.entry_order_type,
            price=self.config.entry_price,
            stop_price=self.config.entry_stop_price,
            size=self.config.total_size,
            priority=1,
            time_in_force=self.config.time_in_force,
            description="Entry order"
        ))

        # Take profit legs (multiple)
        tp_prices = await self._calculate_multi_take_profit_prices(self.config.entry_price)
        for i, tp_price in enumerate(tp_prices):
            size_percent = 100.0 / len(tp_prices)
            legs.append(OCOLeg(
                leg_type=OCOLegType.TAKE_PROFIT,
                side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
                order_type=OrderType.LIMIT,
                price=tp_price,
                size=self.config.total_size * (size_percent / 100),
                priority=i + 2,
                time_in_force=self.config.time_in_force,
                description=f"Take profit {i + 1}"
            ))

        # Stop loss legs (multiple)
        sl_prices = await self._calculate_multi_stop_loss_prices(self.config.entry_price)
        for i, sl_price in enumerate(sl_prices):
            size_percent = 100.0 / len(sl_prices)
            legs.append(OCOLeg(
                leg_type=OCOLegType.STOP_LOSS,
                side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
                order_type=OrderType.STOP,
                stop_price=sl_price,
                size=self.config.total_size * (size_percent / 100),
                priority=len(tp_prices) + i + 2,
                time_in_force=self.config.time_in_force,
                description=f"Stop loss {i + 1}"
            ))

        return legs

    async def _generate_oto_legs(self) -> List[OCOLeg]:
        """Generate OTO (One-Triggers-Other) legs"""
        legs = []

        # Primary order
        legs.append(OCOLeg(
            leg_type=OCOLegType.ENTRY,
            side=self.config.side,
            order_type=self.config.entry_order_type,
            price=self.config.entry_price,
            stop_price=self.config.entry_stop_price,
            size=self.config.total_size,
            priority=1,
            time_in_force=self.config.time_in_force,
            trigger_price=self.config.trigger_price,
            description="Primary order"
        ))

        # Secondary orders (triggered after primary)
        if self.config.chain_orders:
            for i, order_data in enumerate(self.config.chain_orders):
                legs.append(OCOLeg(
                    leg_type=OCOLegType(order_data.get('leg_type', 'take_profit')),
                    side=OrderSide(order_data.get('side', 'sell')),
                    order_type=OrderType(order_data.get('order_type', 'limit')),
                    price=order_data.get('price'),
                    stop_price=order_data.get('stop_price'),
                    size=order_data.get('size', self.config.total_size),
                    priority=i + 2,
                    time_in_force=TimeInForce(order_data.get('time_in_force', 'gtc')),
                    trigger_price=order_data.get('trigger_price'),
                    description=order_data.get('description', f"OTO leg {i + 1}")
                ))

        return legs

    async def _generate_otoco_legs(self) -> List[OCOLeg]:
        """Generate OTOCO (One-Triggers-One-Cancels-Other) legs"""
        legs = await self._generate_oto_legs()

        # Add OCO legs that cancel each other
        # This is a more complex implementation
        # Simplified version: add stop and take profit that cancel each other

        if self.config.take_profit_price:
            legs.append(OCOLeg(
                leg_type=OCOLegType.TAKE_PROFIT,
                side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
                order_type=OrderType.LIMIT,
                price=self.config.take_profit_price,
                size=self.config.total_size * 0.5,
                priority=len(legs) + 1,
                time_in_force=self.config.time_in_force,
                description="OTOCO Take profit"
            ))

        if self.config.stop_loss_price:
            legs.append(OCOLeg(
                leg_type=OCOLegType.STOP_LOSS,
                side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
                order_type=OrderType.STOP,
                stop_price=self.config.stop_loss_price,
                size=self.config.total_size * 0.5,
                priority=len(legs) + 1,
                time_in_force=self.config.time_in_force,
                description="OTOCO Stop loss"
            ))

        return legs

    async def _generate_chain_legs(self) -> List[OCOLeg]:
        """Generate chain of orders"""
        legs = []

        if not self.config.chain_orders:
            return legs

        for i, order_data in enumerate(self.config.chain_orders):
            leg_type = OCOLegType(order_data.get('leg_type', 'entry'))
            side = OrderSide(order_data.get('side', 'buy'))

            legs.append(OCOLeg(
                leg_type=leg_type,
                side=side,
                order_type=OrderType(order_data.get('order_type', 'limit')),
                price=order_data.get('price'),
                stop_price=order_data.get('stop_price'),
                size=order_data.get('size', self.config.total_size / len(self.config.chain_orders)),
                priority=i + 1,
                time_in_force=TimeInForce(order_data.get('time_in_force', 'gtc')),
                trigger_price=order_data.get('trigger_price'),
                description=order_data.get('description', f"Chain leg {i + 1}")
            ))

        return legs

    async def _generate_trailing_legs(self) -> List[OCOLeg]:
        """Generate trailing OCO legs"""
        legs = []

        # Entry leg
        legs.append(OCOLeg(
            leg_type=OCOLegType.ENTRY,
            side=self.config.side,
            order_type=self.config.entry_order_type,
            price=self.config.entry_price,
            size=self.config.total_size,
            priority=1,
            time_in_force=self.config.time_in_force,
            description="Entry order"
        ))

        # Take profit with trailing
        legs.append(OCOLeg(
            leg_type=OCOLegType.TAKE_PROFIT,
            side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=self.config.take_profit_price,
            size=self.config.total_size * 0.5,
            priority=2,
            time_in_force=self.config.time_in_force,
            trailing_distance=self.config.trailing_distance,
            trail_activation=self.config.trailing_activation,
            description="Trailing take profit"
        ))

        # Trailing stop loss
        legs.append(OCOLeg(
            leg_type=OCOLegType.TRAILING_STOP,
            side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.STOP,
            stop_price=self.config.stop_loss_price,
            size=self.config.total_size * 0.5,
            priority=3,
            time_in_force=self.config.time_in_force,
            trailing_distance=self.config.trailing_distance,
            trail_activation=self.config.trailing_activation,
            description="Trailing stop loss"
        ))

        return legs

    async def _generate_scaling_legs(self) -> List[OCOLeg]:
        """Generate scaling OCO legs"""
        legs = []

        if not self.config.scaling_levels:
            # Auto-generate scaling levels
            num_levels = 3
            price_step = 0.01

            for i in range(num_levels):
                price_offset = price_step * (i + 1)
                if self.config.side == OrderSide.BUY:
                    entry_price = self.config.entry_price * (1 - price_offset)
                else:
                    entry_price = self.config.entry_price * (1 + price_offset)

                legs.append(OCOLeg(
                    leg_type=OCOLegType.ENTRY,
                    side=self.config.side,
                    order_type=OrderType.LIMIT,
                    price=entry_price,
                    size=self.config.total_size / num_levels,
                    priority=i + 1,
                    time_in_force=self.config.time_in_force,
                    description=f"Scaling entry {i + 1}"
                ))

        else:
            for i, level_data in enumerate(self.config.scaling_levels):
                legs.append(OCOLeg(
                    leg_type=OCOLegType(level_data.get('leg_type', 'entry')),
                    side=OrderSide(level_data.get('side', self.config.side.value)),
                    order_type=OrderType(level_data.get('order_type', 'limit')),
                    price=level_data.get('price'),
                    stop_price=level_data.get('stop_price'),
                    size=level_data.get('size', self.config.total_size / len(self.config.scaling_levels)),
                    priority=i + 1,
                    time_in_force=TimeInForce(level_data.get('time_in_force', 'gtc')),
                    description=level_data.get('description', f"Scaling level {i + 1}")
                ))

        return legs

    async def _generate_adaptive_legs(self) -> List[OCOLeg]:
        """Generate adaptive OCO legs based on market conditions"""
        # Get market conditions
        volatility = await self._calculate_volatility()
        spread = await self._calculate_spread()

        # Adjust prices based on conditions
        base_entry = self.config.entry_price or self._current_price or 100

        if volatility > 0.02:
            # High volatility, wider ranges
            tp_multiplier = 1 + volatility * 2
            sl_multiplier = 1 + volatility * 1.5
        else:
            # Low volatility, tighter ranges
            tp_multiplier = 1 + 0.02
            sl_multiplier = 1 + 0.01

        # Use standard legs with adaptive prices
        legs = []

        # Entry
        legs.append(OCOLeg(
            leg_type=OCOLegType.ENTRY,
            side=self.config.side,
            order_type=self.config.entry_order_type,
            price=base_entry,
            size=self.config.total_size,
            priority=1,
            time_in_force=self.config.time_in_force,
            description="Adaptive entry"
        ))

        # Adaptive take profit
        if self.config.side == OrderSide.BUY:
            tp_price = base_entry * (1 + 0.02 * tp_multiplier)
        else:
            tp_price = base_entry * (1 - 0.02 * tp_multiplier)

        legs.append(OCOLeg(
            leg_type=OCOLegType.TAKE_PROFIT,
            side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=tp_price,
            size=self.config.total_size * 0.6,
            priority=2,
            time_in_force=self.config.time_in_force,
            description="Adaptive take profit"
        ))

        # Adaptive stop loss
        if self.config.side == OrderSide.BUY:
            sl_price = base_entry * (1 - 0.01 * sl_multiplier)
        else:
            sl_price = base_entry * (1 + 0.01 * sl_multiplier)

        legs.append(OCOLeg(
            leg_type=OCOLegType.STOP_LOSS,
            side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.STOP,
            stop_price=sl_price,
            size=self.config.total_size * 0.4,
            priority=3,
            time_in_force=self.config.time_in_force,
            description="Adaptive stop loss"
        ))

        return legs

    def _filter_and_validate_legs(self, legs: List[OCOLeg]) -> List[OCOLeg]:
        """Filter and validate OCO legs"""
        validated = []
        total_size = 0

        # Sort by priority
        legs.sort(key=lambda x: x.priority)

        for leg in legs:
            # Validate size
            if leg.size <= 0:
                continue

            # Validate price/stop price combination
            if leg.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and leg.price is None:
                continue

            if leg.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and leg.stop_price is None:
                continue

            validated.append(leg)
            total_size += leg.size

        # Normalize sizes if needed
        if total_size > 0 and abs(total_size - self.config.total_size) > 0.001:
            for leg in validated:
                leg.size = (leg.size / total_size) * self.config.total_size

        return validated

    async def _submit_orders(self):
        """Submit all OCO legs"""
        if not self._broker:
            return

        for leg_index, leg in enumerate(self._legs):
            try:
                order_params = {
                    'symbol': self.config.symbol,
                    'side': leg.side,
                    'quantity': leg.size,
                    'order_type': leg.order_type,
                    'time_in_force': leg.time_in_force,
                    'client_order_id': f"{self.id}_{leg_index}_{leg.leg_type.value}"
                }

                if leg.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                    order_params['price'] = leg.price

                if leg.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                    order_params['stop_price'] = leg.stop_price

                # Add trailing parameters if applicable
                if leg.trailing_distance:
                    order_params['trailing_distance'] = leg.trailing_distance
                if leg.trail_activation:
                    order_params['trailing_activation'] = leg.trail_activation

                result = await self._broker.place_order(**order_params)
                self._order_ids[leg_index] = result.get('order_id')

                logger.debug(f"Submitted OCO leg {leg_index} ({leg.leg_type.value})")

            except Exception as e:
                logger.error(f"Failed to submit OCO leg {leg_index}: {e}")

    async def _check_legs_trigger(self, current_price: float) -> bool:
        """Check if any legs should trigger"""
        triggered = False

        for leg_index in self._active_legs:
            if leg_index in self._executed_legs:
                continue

            order_id = self._order_ids.get(leg_index)
            if not order_id:
                continue

            try:
                status = await self._broker.get_order_status(order_id)

                if status.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                    await self._execute_leg(leg_index, status)
                    triggered = True

                elif status.get('status') in ['REJECTED', 'EXPIRED']:
                    await self._handle_leg_failure(leg_index, status)

            except Exception as e:
                logger.error(f"Failed to check OCO leg {leg_index}: {e}")

        return triggered

    async def _execute_leg(self, leg_index: int, status: Dict[str, Any]):
        """Execute an OCO leg"""
        leg = self._legs[leg_index]

        filled_size = status.get('filled_quantity', leg.size)
        exec_price = status.get('price', leg.price or leg.stop_price or 0)

        # Update metrics
        self._executed_size += filled_size
        self._remaining_size -= filled_size
        self._executed_legs.append(leg_index)
        self._active_legs.remove(leg_index)

        self._metrics.legs_executed += 1
        self._metrics.executed_size = self._executed_size
        self._metrics.remaining_size = self._remaining_size

        # Update entry price if this is an entry leg
        if leg.leg_type == OCOLegType.ENTRY:
            self._entry_price_actual = exec_price
            self._metrics.entry_price = exec_price

        # Calculate P&L
        if leg.leg_type == OCOLegType.TAKE_PROFIT and self._entry_price_actual:
            profit = (exec_price - self._entry_price_actual) * filled_size
            self._metrics.realized_pnl += profit
            self._profit_taken = True

        if leg.leg_type == OCOLegType.STOP_LOSS and self._entry_price_actual:
            loss = (self._entry_price_actual - exec_price) * filled_size
            self._metrics.realized_pnl += loss
            self._stop_triggered = True

        # Cancel other legs if OCO condition
        await self._cancel_oco_legs(leg_index)

        logger.info(f"OCO leg {leg_index} executed at {exec_price}, size: {filled_size}")

        # Check if fully executed
        if self._executed_size >= self.config.total_size * 0.99:
            self._state = OCOState.EXECUTED
            logger.info(f"OCO order {self.id} fully executed")

    async def _cancel_oco_legs(self, executed_leg_index: int):
        """Cancel other legs in OCO relationship"""
        for leg_index in self._active_legs:
            if leg_index == executed_leg_index:
                continue

            # Check if this leg should be cancelled
            if self._should_cancel_leg(executed_leg_index, leg_index):
                order_id = self._order_ids.get(leg_index)
                if order_id:
                    try:
                        await self._broker.cancel_order(order_id)
                        self._cancelled_legs.append(leg_index)
                        self._active_legs.remove(leg_index)
                        logger.debug(f"Cancelled OCO leg {leg_index} due to leg {executed_leg_index}")
                    except Exception as e:
                        logger.error(f"Failed to cancel OCO leg {leg_index}: {e}")

    def _should_cancel_leg(self, executed_leg: int, other_leg: int) -> bool:
        """Determine if a leg should be cancelled"""
        executed = self._legs[executed_leg]
        other = self._legs[other_leg]

        # Standard OCO: cancel opposite leg
        if self.config.oco_type == OCOType.STANDARD:
            return (executed.leg_type == OCOLegType.TAKE_PROFIT and other.leg_type == OCOLegType.STOP_LOSS) or \
                   (executed.leg_type == OCOLegType.STOP_LOSS and other.leg_type == OCOLegType.TAKE_PROFIT)

        # Bracket: cancel opposite leg if partial
        if self.config.oco_type == OCOType.BRACKET:
            if executed.leg_type == OCOLegType.TAKE_PROFIT:
                return other.leg_type == OCOLegType.STOP_LOSS
            if executed.leg_type == OCOLegType.STOP_LOSS:
                return other.leg_type == OCOLegType.TAKE_PROFIT

        # OTO: cancel triggered legs
        if self.config.oco_type == OCOType.OTO:
            return other.leg_type in [OCOLegType.TAKE_PROFIT, OCOLegType.STOP_LOSS]

        # OTOCO: cancel opposing leg
        if self.config.oco_type == OCOType.OTOCO:
            return (executed.leg_type == OCOLegType.TAKE_PROFIT and other.leg_type == OCOLegType.STOP_LOSS) or \
                   (executed.leg_type == OCOLegType.STOP_LOSS and other.leg_type == OCOLegType.TAKE_PROFIT)

        # Chain: cancel based on condition
        if self.config.oco_type == OCOType.CHAIN:
            return True  # Chain cancels all after execution

        # Trailing: keep trailing legs active
        if self.config.oco_type == OCOType.TRAILING:
            if other.leg_type == OCOLegType.TRAILING_STOP:
                return False
            return executed.leg_type in [OCOLegType.TAKE_PROFIT, OCOLegType.TRAILING_STOP]

        # Scaling: don't cancel other scaling legs
        if self.config.oco_type == OCOType.SCALING:
            return False

        # Adaptive: cancel based on conditions
        if self.config.oco_type == OCOType.ADAPTIVE:
            return True

        return True

    async def _handle_leg_failure(self, leg_index: int, status: Dict[str, Any]):
        """Handle a failed leg"""
        self._active_legs.remove(leg_index)
        self._cancelled_legs.append(leg_index)

        logger.warning(f"OCO leg {leg_index} failed: {status.get('status')}")

        # Check if we should retry
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries and leg_index in self._cancelled_legs:
            try:
                # Retry the order
                order_params = {
                    'symbol': self.config.symbol,
                    'side': self._legs[leg_index].side,
                    'quantity': self._legs[leg_index].size,
                    'order_type': self._legs[leg_index].order_type,
                    'time_in_force': self._legs[leg_index].time_in_force,
                    'client_order_id': f"{self.id}_{leg_index}_retry_{retry_count}"
                }

                leg = self._legs[leg_index]
                if leg.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                    order_params['price'] = leg.price
                if leg.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                    order_params['stop_price'] = leg.stop_price

                result = await self._broker.place_order(**order_params)
                self._order_ids[leg_index] = result.get('order_id')
                self._active_legs.append(leg_index)
                self._cancelled_legs.remove(leg_index)

                logger.info(f"Retried OCO leg {leg_index} successfully")
                break

            except Exception as e:
                retry_count += 1
                logger.warning(f"Retry {retry_count} for leg {leg_index} failed: {e}")
                await asyncio.sleep(0.5 * retry_count)

    async def _check_oto_triggers(self, current_price: float):
        """Check OTO triggers"""
        for leg_index in self._active_legs:
            leg = self._legs[leg_index]
            if leg.trigger_price is None:
                continue

            triggered = False
            if leg.leg_type == OCOLegType.ENTRY:
                if leg.side == OrderSide.BUY:
                    triggered = current_price <= leg.trigger_price
                else:
                    triggered = current_price >= leg.trigger_price

            if triggered:
                self._triggered_legs.append(leg_index)
                # Execute the triggered leg
                await self._execute_triggered_leg(leg_index)

    async def _execute_triggered_leg(self, leg_index: int):
        """Execute a triggered OTO leg"""
        leg = self._legs[leg_index]

        try:
            result = await self._broker.place_order(
                symbol=self.config.symbol,
                side=leg.side,
                order_type=leg.order_type,
                quantity=leg.size,
                price=leg.price,
                stop_price=leg.stop_price,
                time_in_force=leg.time_in_force,
                client_order_id=f"{self.id}_{leg_index}_oto"
            )

            self._order_ids[leg_index] = result.get('order_id')
            logger.info(f"OTO leg {leg_index} triggered at {leg.trigger_price}")

        except Exception as e:
            logger.error(f"Failed to execute OTO leg {leg_index}: {e}")

    async def _check_bracket_trigger(self, current_price: float):
        """Check bracket order triggers"""
        # Check if entry has been triggered
        entry_leg_index = None
        for leg_index in self._active_legs:
            if self._legs[leg_index].leg_type == OCOLegType.ENTRY:
                entry_leg_index = leg_index
                break

        if entry_leg_index is None:
            return

        entry_leg = self._legs[entry_leg_index]

        # Check if entry price is reached
        entry_triggered = False
        if entry_leg.side == OrderSide.BUY:
            if current_price <= entry_leg.price:
                entry_triggered = True
        else:
            if current_price >= entry_leg.price:
                entry_triggered = True

        if entry_triggered:
            # Execute entry
            await self._execute_leg(entry_leg_index, {
                'filled_quantity': entry_leg.size,
                'price': current_price
            })

            # Place take profit and stop loss
            await self._place_bracket_orders(current_price)

    async def _place_bracket_orders(self, entry_price: float):
        """Place bracket orders after entry"""
        # Take profit
        tp_price = self._calculate_take_profit_price(entry_price)
        if tp_price:
            tp_leg = OCOLeg(
                leg_type=OCOLegType.TAKE_PROFIT,
                side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
                order_type=OrderType.LIMIT,
                price=tp_price,
                size=self.config.total_size * (self.config.take_profit_size_percent / 100),
                priority=2,
                time_in_force=self.config.time_in_force,
                description="Bracket take profit"
            )
            self._legs.append(tp_leg)
            await self._submit_leg(len(self._legs) - 1, tp_leg)

        # Stop loss
        sl_price = self._calculate_stop_loss_price(entry_price)
        if sl_price:
            sl_leg = OCOLeg(
                leg_type=OCOLegType.STOP_LOSS,
                side=OrderSide.SELL if self.config.side == OrderSide.BUY else OrderSide.BUY,
                order_type=OrderType.STOP,
                stop_price=sl_price,
                size=self.config.total_size * (self.config.stop_loss_size_percent / 100),
                priority=3,
                time_in_force=self.config.time_in_force,
                description="Bracket stop loss"
            )
            self._legs.append(sl_leg)
            await self._submit_leg(len(self._legs) - 1, sl_leg)

    async def _submit_leg(self, leg_index: int, leg: OCOLeg):
        """Submit a single leg"""
        if not self._broker:
            return

        try:
            order_params = {
                'symbol': self.config.symbol,
                'side': leg.side,
                'quantity': leg.size,
                'order_type': leg.order_type,
                'time_in_force': leg.time_in_force,
                'client_order_id': f"{self.id}_{leg_index}_{leg.leg_type.value}"
            }

            if leg.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                order_params['price'] = leg.price
            if leg.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                order_params['stop_price'] = leg.stop_price

            result = await self._broker.place_order(**order_params)
            self._order_ids[leg_index] = result.get('order_id')
            self._active_legs.append(leg_index)

        except Exception as e:
            logger.error(f"Failed to submit OCO leg {leg_index}: {e}")

    async def _update_trailing_orders(self, current_price: float):
        """Update trailing OCO orders"""
        for leg_index in self._active_legs:
            leg = self._legs[leg_index]
            if not leg.trailing_distance:
                continue

            # Check activation
            if leg.trail_activation:
                if leg.side == OrderSide.BUY:
                    if current_price < leg.trail_activation:
                        continue
                else:
                    if current_price > leg.trail_activation:
                        continue

            # Update trailing price
            order_id = self._order_ids.get(leg_index)
            if not order_id:
                continue

            try:
                if leg.leg_type == OCOLegType.TAKE_PROFIT:
                    new_price = current_price * (1 + leg.trailing_distance)
                    if leg.side == OrderSide.SELL:
                        if new_price > leg.price:
                            leg.price = round_to_tick_size(new_price)
                            await self._broker.update_order(order_id, price=leg.price)
                elif leg.leg_type == OCOLegType.TRAILING_STOP:
                    new_stop = current_price * (1 - leg.trailing_distance)
                    if leg.side == OrderSide.SELL:
                        if new_stop < leg.stop_price:
                            leg.stop_price = round_to_tick_size(new_stop)
                            await self._broker.update_order(order_id, stop_price=leg.stop_price)

            except Exception as e:
                logger.error(f"Failed to update trailing order {order_id}: {e}")

    async def _adjust_adaptive_orders(self, current_price: float):
        """Adjust adaptive OCO orders"""
        if len(self._price_history) < 10:
            return

        # Calculate market conditions
        volatility = await self._calculate_volatility()
        trend = self._calculate_trend()

        # Adjust take profit and stop loss
        for leg_index in self._active_legs:
            leg = self._legs[leg_index]
            order_id = self._order_ids.get(leg_index)
            if not order_id:
                continue

            if leg.leg_type == OCOLegType.TAKE_PROFIT:
                # Adjust take profit based on volatility and trend
                adjustment = 1 + volatility * trend * 0.1
                if self.config.side == OrderSide.BUY:
                    new_price = current_price * (1 + 0.02 * adjustment)
                else:
                    new_price = current_price * (1 - 0.02 * adjustment)

                leg.price = round_to_tick_size(new_price)
                try:
                    await self._broker.update_order(order_id, price=leg.price)
                except Exception as e:
                    logger.error(f"Failed to update adaptive TP {order_id}: {e}")

            elif leg.leg_type == OCOLegType.STOP_LOSS:
                # Adjust stop loss based on volatility
                adjustment = 1 + volatility * 0.5
                if self.config.side == OrderSide.BUY:
                    new_stop = current_price * (1 - 0.01 * adjustment)
                else:
                    new_stop = current_price * (1 + 0.01 * adjustment)

                # Don't move stop loss against the trade
                if self.config.side == OrderSide.BUY:
                    if new_stop > leg.stop_price:
                        continue
                else:
                    if new_stop < leg.stop_price:
                        continue

                leg.stop_price = round_to_tick_size(new_stop)
                try:
                    await self._broker.update_order(order_id, stop_price=leg.stop_price)
                except Exception as e:
                    logger.error(f"Failed to update adaptive SL {order_id}: {e}")

    async def _check_position_close(self):
        """Check if position has closed"""
        try:
            position = await self._broker.get_position(self.config.symbol)
            if position and position.get('size', 0) == 0:
                # Position closed, cancel all pending orders
                await self.cancel(cancel_all=True)
                logger.info(f"Position closed for {self.config.symbol}, cancelling OCO")
        except Exception as e:
            logger.error(f"Failed to check position: {e}")

    def _calculate_take_profit_price(self, entry_price: float) -> Optional[float]:
        """Calculate take profit price"""
        if self.config.take_profit_price:
            return self.config.take_profit_price

        if self.config.take_profit_percent:
            if self.config.side == OrderSide.BUY:
                return entry_price * (1 + self.config.take_profit_percent / 100)
            else:
                return entry_price * (1 - self.config.take_profit_percent / 100)

        # Calculate based on risk-reward ratio
        stop_loss = self._calculate_stop_loss_price(entry_price)
        if stop_loss and self.config.risk_reward_ratio:
            risk = abs(entry_price - stop_loss)
            reward = risk * self.config.risk_reward_ratio
            if self.config.side == OrderSide.BUY:
                return entry_price + reward
            else:
                return entry_price - reward

        return None

    def _calculate_stop_loss_price(self, entry_price: float) -> Optional[float]:
        """Calculate stop loss price"""
        if self.config.stop_loss_price:
            return self.config.stop_loss_price

        if self.config.stop_loss_percent:
            if self.config.side == OrderSide.BUY:
                return entry_price * (1 - self.config.stop_loss_percent / 100)
            else:
                return entry_price * (1 + self.config.stop_loss_percent / 100)

        # Calculate based on risk
        if self.config.risk_amount:
            if self.config.side == OrderSide.BUY:
                return entry_price - (self.config.risk_amount / self.config.total_size)
            else:
                return entry_price + (self.config.risk_amount / self.config.total_size)

        if self.config.max_risk_percent:
            if self.config.side == OrderSide.BUY:
                return entry_price * (1 - self.config.max_risk_percent / 100)
            else:
                return entry_price * (1 + self.config.max_risk_percent / 100)

        return None

    async def _calculate_multi_take_profit_prices(self, entry_price: float) -> List[float]:
        """Calculate multiple take profit prices"""
        prices = []
        num_targets = 3

        for i in range(1, num_targets + 1):
            percentage = i * 0.5  # 0.5%, 1%, 1.5%
            if self.config.side == OrderSide.BUY:
                price = entry_price * (1 + percentage / 100)
            else:
                price = entry_price * (1 - percentage / 100)
            prices.append(round_to_tick_size(price))

        return prices

    async def _calculate_multi_stop_loss_prices(self, entry_price: float) -> List[float]:
        """Calculate multiple stop loss prices"""
        prices = []
        num_targets = 2

        for i in range(1, num_targets + 1):
            percentage = i * 0.5  # 0.5%, 1%
            if self.config.side == OrderSide.BUY:
                price = entry_price * (1 - percentage / 100)
            else:
                price = entry_price * (1 + percentage / 100)
            prices.append(round_to_tick_size(price))

        return prices

    async def _calculate_volatility(self) -> float:
        """Calculate current volatility"""
        if len(self._price_history) < 20:
            return 0.01

        returns = []
        for i in range(1, 20):
            if self._price_history[-i-1] != 0:
                returns.append((self._price_history[-i] - self._price_history[-i-1]) / self._price_history[-i-1])

        if not returns:
            return 0.01

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return variance ** 0.5

    def _calculate_trend(self) -> float:
        """Calculate price trend"""
        if len(self._price_history) < 10:
            return 0

        recent_avg = sum(self._price_history[-5:]) / 5
        older_avg = sum(self._price_history[-10:-5]) / 5

        if older_avg == 0:
            return 0

        return (recent_avg - older_avg) / older_avg

    async def _calculate_spread(self) -> float:
        """Calculate current spread"""
        # Simplified - would get from market data in production
        return 0.001

    async def _update_metrics(self):
        """Update metrics"""
        if self._entry_price_actual and self._current_price:
            if self.config.side == OrderSide.BUY:
                self._metrics.unrealized_pnl = (self._current_price - self._entry_price_actual) * self._executed_size
            else:
                self._metrics.unrealized_pnl = (self._entry_price_actual - self._current_price) * self._executed_size

        self._metrics.total_pnl = self._metrics.realized_pnl + self._metrics.unrealized_pnl

        # Update drawdown/runup
        if self._metrics.total_pnl < 0:
            self._metrics.max_drawdown = min(self._metrics.max_drawdown, self._metrics.total_pnl)
        else:
            self._metrics.max_runup = max(self._metrics.max_runup, self._metrics.total_pnl)

        # Fill rate
        if self.config.total_size > 0:
            self._metrics.fill_rate = (self._executed_size / self.config.total_size) * 100

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
        """Convert OCO order to dictionary"""
        return {
            'id': self.id,
            'state': self._state.value,
            'config': self.config.model_dump(),
            'metrics': self._metrics.model_dump(),
            'current_price': self._current_price,
            'entry_price_actual': self._entry_price_actual,
            'legs': [leg.model_dump() for leg in self._legs],
            'executed_legs': self._executed_legs,
            'cancelled_legs': self._cancelled_legs,
            'active_legs': self._active_legs,
            'order_ids': self._order_ids,
            'executed_size': self._executed_size,
            'remaining_size': self._remaining_size,
            'stop_triggered': self._stop_triggered,
            'profit_taken': self._profit_taken,
            'triggered_legs': self._triggered_legs
        }

    @classmethod
    async def from_dict(
        cls,
        data: Dict[str, Any],
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ) -> 'OCOOrder':
        """Create OCO order from dictionary"""
        config = OCOConfig(**data.get('config', {}))
        oco_order = cls(config=config, broker=broker, order_manager=order_manager)

        # Restore state
        oco_order._state = OCOState(data.get('state', 'pending'))
        oco_order._current_price = data.get('current_price')
        oco_order._entry_price_actual = data.get('entry_price_actual')
        oco_order._executed_size = data.get('executed_size', 0)
        oco_order._remaining_size = data.get('remaining_size', 0)
        oco_order._executed_legs = data.get('executed_legs', [])
        oco_order._cancelled_legs = data.get('cancelled_legs', [])
        oco_order._active_legs = data.get('active_legs', [])
        oco_order._triggered_legs = data.get('triggered_legs', [])
        oco_order._stop_triggered = data.get('stop_triggered', False)
        oco_order._profit_taken = data.get('profit_taken', False)

        # Restore legs
        if data.get('legs'):
            oco_order._legs = [OCOLeg(**leg) for leg in data.get('legs')]

        # Restore order IDs
        if data.get('order_ids'):
            oco_order._order_ids = {int(k): v for k, v in data.get('order_ids').items()}

        # Restore metrics
        if data.get('metrics'):
            oco_order._metrics = OCOMetrics(**data.get('metrics'))

        return oco_order

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cancel()
        await self.stop_price_monitoring()
