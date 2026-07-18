"""
NEXUS AI TRADING SYSTEM - Smart Take Profit Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/smart_take_profit.py
Version: 1.0.0
Description: Advanced smart take profit implementation with full API integration
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable

from pydantic import BaseModel, Field, ConfigDict, validator

from shared.types.trading import OrderSide, OrderType, OrderStatus, TimeInForce
from shared.helpers.trading_helpers import (
    calculate_percentage_change,
    calculate_price_distance,
    round_to_tick_size,
    calculate_rsi,
    calculate_macd
)
from shared.constants.trading_constants import (
    MIN_PROFIT_TARGET,
    DEFAULT_RISK_REWARD_RATIO,
    MAX_TAKE_PROFIT_ORDERS
)
from shared.interfaces.broker import BrokerInterface
from trading.smart_orders.base_order import SmartOrder, SmartOrderConfig
from trading.smart_orders.order_manager import OrderManager

logger = logging.getLogger(__name__)


class TakeProfitType(str, Enum):
    """Types of take profit mechanisms"""
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    ATR = "atr"
    VOLATILITY = "volatility"
    RESISTANCE = "resistance"
    SUPPORT = "support"
    PATTERN = "pattern"
    DYNAMIC = "dynamic"
    RATIO = "ratio"


class TakeProfitMode(str, Enum):
    """Take profit modes"""
    SINGLE = "single"  # Single take profit level
    MULTI = "multi"  # Multiple take profit levels
    TRAILING = "trailing"  # Trailing take profit
    SCALING = "scaling"  # Scale out at levels
    ADAPTIVE = "adaptive"  # Adaptive to market conditions


class TakeProfitDistribution(str, Enum):
    """Distribution methods for multi-level take profits"""
    LINEAR = "linear"  # Equal distribution
    FIBONACCI = "fibonacci"  # Fibonacci-based distribution
    WEIGHTED = "weighted"  # Weighted distribution
    DYNAMIC = "dynamic"  # Dynamic distribution based on conditions


class TakeProfitLevel(BaseModel):
    """Individual take profit level configuration"""
    price: float = Field(..., description="Take profit price")
    size_percent: float = Field(..., description="Percentage of position to close at this level")
    priority: int = Field(1, description="Priority order (1 = first)")
    type: TakeProfitType = Field(default=TakeProfitType.FIXED)
    trailing: bool = Field(False, description="Whether this level is trailing")
    trailing_distance: Optional[float] = Field(None, description="Trailing distance for this level")
    minimum_profit: Optional[float] = Field(None, description="Minimum profit required")
    description: Optional[str] = Field(None, description="Description of this level")


class TakeProfitMetrics(BaseModel):
    """Metrics for take profit performance analysis"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    entry_price: Optional[float] = Field(None, description="Entry price")
    current_price: Optional[float] = Field(None, description="Current market price")
    highest_price: Optional[float] = Field(None, description="Highest price reached")
    lowest_price: Optional[float] = Field(None, description="Lowest price reached")
    
    achieved_levels: List[float] = Field(default_factory=list, description="Achieved take profit levels")
    achieved_percent: float = Field(0.0, description="Percentage of position closed")
    total_profit: float = Field(0.0, description="Total profit realized")
    total_profit_percent: float = Field(0.0, description="Total profit percentage")
    
    max_favorable_excursion: float = Field(0.0, description="Maximum favorable price movement")
    max_adverse_excursion: float = Field(0.0, description="Maximum adverse price movement")
    
    time_to_first_target: Optional[datetime] = Field(None, description="Time to reach first target")
    time_to_full_target: Optional[datetime] = Field(None, description="Time to reach full target")
    
    partial_fills: int = Field(0, description="Number of partial fills")
    full_fills: int = Field(0, description="Number of full fills")
    
    avg_fill_price: Optional[float] = Field(None, description="Average fill price")
    slippage_total: float = Field(0.0, description="Total slippage")


class SmartTakeProfitConfig(SmartOrderConfig):
    """Configuration for smart take profit order"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    take_profit_type: TakeProfitType = Field(default=TakeProfitType.PERCENTAGE)
    mode: TakeProfitMode = Field(default=TakeProfitMode.SINGLE)
    distribution: TakeProfitDistribution = Field(default=TakeProfitDistribution.LINEAR)

    # Single target settings
    target_price: Optional[float] = Field(None, description="Single target price")
    target_percent: Optional[float] = Field(None, description="Single target percentage")
    risk_reward_ratio: float = Field(DEFAULT_RISK_REWARD_RATIO, description="Risk-reward ratio")

    # Multi-target settings
    levels: List[TakeProfitLevel] = Field(default_factory=list, description="Take profit levels")
    number_of_levels: int = Field(3, description="Number of levels for auto-generation")
    min_level_distance: float = Field(0.01, description="Minimum distance between levels")

    # Distribution settings
    level_distribution: Dict[str, float] = Field(default_factory=dict, description="Distribution percentages")

    # ATR settings
    atr_multiplier: float = Field(2.0, description="ATR multiplier for targets")
    atr_period: int = Field(14, description="ATR calculation period")

    # Volatility settings
    volatility_multiplier: float = Field(1.5, description="Volatility multiplier for targets")
    volatility_window: int = Field(20, description="Volatility window")

    # Resistance/Support settings
    resistance_levels: List[float] = Field(default_factory=list, description="Resistance levels")
    support_levels: List[float] = Field(default_factory=list, description="Support levels")
    level_tolerance: float = Field(0.005, description="Tolerance for levels (0.5%)")

    # Pattern settings
    fibonacci_levels: List[float] = Field(
        default=[0.236, 0.382, 0.5, 0.618, 0.786],
        description="Fibonacci levels"
    )

    # Dynamic settings
    min_target_distance: Optional[float] = Field(None, description="Minimum target distance")
    max_target_distance: Optional[float] = Field(None, description="Maximum target distance")
    adaptation_speed: float = Field(0.5, description="Adaptation speed (0-1)")

    # Trailing take profit settings
    enable_trailing: bool = Field(False, description="Enable trailing take profit")
    trailing_activation: Optional[float] = Field(None, description="Activation price for trailing")
    trailing_step: float = Field(0.01, description="Step size for trailing")

    # Order settings
    order_size: float = Field(..., description="Size of the order")
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    expire_after: Optional[timedelta] = Field(None, description="Expiration time")
    max_slippage: float = Field(0.01, description="Maximum allowed slippage")
    use_limit_orders: bool = Field(True, description="Use limit orders for take profit")
    limit_offset: Optional[float] = Field(None, description="Offset for limit orders")
    allow_partial_fill: bool = Field(True, description="Allow partial fills")

    # Risk settings
    min_profit_target: float = Field(MIN_PROFIT_TARGET, description="Minimum profit target")
    max_loss_allowed: Optional[float] = Field(None, description="Maximum loss allowed")
    close_on_breakeven: bool = Field(False, description="Close at breakeven if target not reached")
    breakeven_after_time: Optional[timedelta] = Field(None, description="Time to wait before breakeven")
    breakeven_buffer: float = Field(0.001, description="Buffer for breakeven (0.1%)")

    @validator('target_percent')
    def validate_target_percent(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Target percentage must be positive")
        return v

    @validator('atr_multiplier')
    def validate_atr(cls, v):
        if v <= 0:
            raise ValueError("ATR multiplier must be positive")
        return v

    @validator('number_of_levels')
    def validate_level_count(cls, v):
        if v < 1 or v > MAX_TAKE_PROFIT_ORDERS:
            raise ValueError(f"Number of levels must be between 1 and {MAX_TAKE_PROFIT_ORDERS}")
        return v

    @validator('min_level_distance')
    def validate_level_distance(cls, v):
        if v < 0:
            raise ValueError("Minimum level distance must be non-negative")
        return v

    @validator('adaptation_speed')
    def validate_adaptation(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Adaptation speed must be between 0 and 1")
        return v


class TakeProfitExecution(BaseModel):
    """Execution result for take profit"""
    level_index: int
    level_price: float
    executed_price: float
    executed_size: float
    total_profit: float
    status: OrderStatus
    timestamp: datetime
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class SmartTakeProfit(SmartOrder):
    """
    Advanced smart take profit implementation with full API integration.
    
    Supports multiple take profit mechanisms:
    - Fixed price targets
    - Percentage-based targets
    - ATR-based targets
    - Volatility-based targets
    - Resistance/Support levels
    - Fibonacci patterns
    - Dynamic adaptation
    
    Features:
    - Multiple target levels with distribution
    - Trailing take profit
    - Adaptive target adjustment
    - Full broker API integration
    - Performance metrics tracking
    - Real-time price monitoring
    """

    def __init__(
        self,
        config: SmartTakeProfitConfig,
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ):
        """
        Initialize smart take profit order.

        Args:
            config: Take profit configuration
            broker: Optional broker interface for execution
            order_manager: Optional order manager for coordination
        """
        super().__init__(config=config, broker=broker, order_manager=order_manager)
        self.config = config
        self._metrics = TakeProfitMetrics()
        self._current_price: Optional[float] = None
        self._entry_price: Optional[float] = None
        self._trade_direction: Optional[OrderSide] = None
        self._position_size: Optional[float] = None
        self._remaining_size: Optional[float] = None
        self._levels: List[TakeProfitLevel] = []
        self._order_ids: Dict[int, str] = {}  # level_index -> order_id
        self._executed_levels: List[int] = []
        self._order_queue: List[Dict[str, Any]] = []
        self._subscription_id: Optional[str] = None

        # Price history
        self._price_history: List[float] = []
        self._timestamp_history: List[datetime] = []
        self._max_history_length = 1000

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(f"Initialized SmartTakeProfit with ID: {self.id}")

    async def activate(
        self,
        price: float,
        direction: OrderSide,
        size: float,
        stop_loss: Optional[float] = None
    ) -> bool:
        """
        Activate the take profit order.

        Args:
            price: Entry price
            direction: Trade direction (BUY/SELL)
            size: Position size
            stop_loss: Optional stop loss price

        Returns:
            bool: True if activated successfully
        """
        async with self._lock:
            if self._state in ['ACTIVE', 'EXECUTED']:
                logger.warning(f"Take profit {self.id} already active or executed")
                return False

            self._entry_price = price
            self._trade_direction = direction
            self._position_size = size
            self._remaining_size = size

            # Generate take profit levels
            self._levels = await self._generate_levels(price, stop_loss)

            if not self._levels:
                logger.error(f"No take profit levels generated for {self.id}")
                return False

            # Set metrics
            self._metrics.entry_price = price
            self._metrics.current_price = price
            self._metrics.highest_price = price
            self._metrics.lowest_price = price

            self._state = 'ACTIVE'
            self._current_price = price

            # Submit orders
            if self._broker:
                await self._submit_orders()

            logger.info(
                f"Take profit {self.id} activated at price {price}, "
                f"levels: {len(self._levels)}, direction: {direction.value}"
            )

            return True

    async def update_price(self, new_price: float, timestamp: Optional[datetime] = None) -> List[float]:
        """
        Update current price and check take profit conditions.

        Args:
            new_price: Current market price
            timestamp: Optional timestamp of price update

        Returns:
            List[float]: List of achieved level prices
        """
        async with self._lock:
            if self._state not in ['ACTIVE', 'PENDING']:
                return []

            self._current_price = new_price
            self._metrics.current_price = new_price

            # Update price history
            self._price_history.append(new_price)
            self._timestamp_history.append(timestamp or datetime.utcnow())
            if len(self._price_history) > self._max_history_length:
                self._price_history.pop(0)
                self._timestamp_history.pop(0)

            # Update highest/lowest
            if self._trade_direction == OrderSide.BUY:
                if new_price > (self._metrics.highest_price or 0):
                    self._metrics.highest_price = new_price
                if self._metrics.lowest_price is None or new_price < self._metrics.lowest_price:
                    self._metrics.lowest_price = new_price
            else:  # SELL
                if self._metrics.lowest_price is None or new_price < (self._metrics.lowest_price or float('inf')):
                    self._metrics.lowest_price = new_price
                if new_price > (self._metrics.highest_price or 0):
                    self._metrics.highest_price = new_price

            # Update metrics
            self._metrics.max_favorable_excursion = max(
                self._metrics.max_favorable_excursion,
                abs(new_price - self._entry_price) / self._entry_price * 100
            )

            # Check if we should update trailing levels
            if self.config.enable_trailing:
                await self._update_trailing_levels(new_price)

            # Check if any levels are reached
            achieved_levels = await self._check_and_execute_levels(new_price)

            return achieved_levels

    async def check_conditions(self, price: Optional[float] = None) -> bool:
        """
        Check if take profit conditions are met.

        Args:
            price: Current price to check

        Returns:
            bool: True if any conditions met
        """
        check_price = price or self._current_price
        if check_price is None:
            return False

        async with self._lock:
            if self._state != 'ACTIVE':
                return False

            achieved = await self._check_and_execute_levels(check_price)
            return len(achieved) > 0

    async def cancel(self) -> bool:
        """
        Cancel the take profit order.

        Returns:
            bool: True if cancelled successfully
        """
        async with self._lock:
            if self._state == 'CANCELLED':
                return False

            self._state = 'CANCELLED'

            # Cancel all orders
            for level_index, order_id in self._order_ids.items():
                try:
                    await self._broker.cancel_order(order_id)
                    logger.debug(f"Cancelled order {order_id} for level {level_index}")
                except Exception as e:
                    logger.error(f"Failed to cancel order {order_id}: {e}")

            self._order_ids.clear()
            logger.info(f"Take profit {self.id} cancelled")

            return True

    async def get_metrics(self) -> TakeProfitMetrics:
        """Get current take profit metrics"""
        async with self._lock:
            return self._metrics.model_copy()

    def get_current_levels(self) -> List[TakeProfitLevel]:
        """Get current take profit levels"""
        return self._levels

    def get_remaining_size(self) -> Optional[float]:
        """Get remaining position size"""
        return self._remaining_size

    def get_achieved_percent(self) -> float:
        """Get percentage of position closed"""
        return self._metrics.achieved_percent

    def get_total_profit(self) -> float:
        """Get total profit realized"""
        return self._metrics.total_profit

    async def get_unfilled_orders(self) -> List[Dict[str, Any]]:
        """Get unfilled orders"""
        unfilled = []
        for level_index, order_id in self._order_ids.items():
            try:
                status = await self._broker.get_order_status(order_id)
                if status.get('status') in ['PENDING', 'WORKING', 'PARTIALLY_FILLED']:
                    unfilled.append({
                        'level_index': level_index,
                        'order_id': order_id,
                        'status': status
                    })
            except Exception as e:
                logger.error(f"Failed to get status for order {order_id}: {e}")
        return unfilled

    async def _generate_levels(self, entry_price: float, stop_loss: Optional[float]) -> List[TakeProfitLevel]:
        """Generate take profit levels based on configuration"""
        levels = []

        if self.config.mode == TakeProfitMode.SINGLE:
            levels = await self._generate_single_level(entry_price, stop_loss)

        elif self.config.mode == TakeProfitMode.MULTI:
            levels = await self._generate_multi_levels(entry_price, stop_loss)

        elif self.config.mode == TakeProfitMode.TRAILING:
            levels = await self._generate_trailing_levels(entry_price, stop_loss)

        elif self.config.mode == TakeProfitMode.SCALING:
            levels = await self._generate_scaling_levels(entry_price, stop_loss)

        elif self.config.mode == TakeProfitMode.ADAPTIVE:
            levels = await self._generate_adaptive_levels(entry_price, stop_loss)

        # Filter and validate levels
        levels = self._filter_and_validate_levels(levels, entry_price)

        return levels

    async def _generate_single_level(self, entry_price: float, stop_loss: Optional[float]) -> List[TakeProfitLevel]:
        """Generate single take profit level"""
        target_price = None

        if self.config.target_price:
            target_price = self.config.target_price

        elif self.config.target_percent:
            if self._trade_direction == OrderSide.BUY:
                target_price = entry_price * (1 + self.config.target_percent / 100)
            else:
                target_price = entry_price * (1 - self.config.target_percent / 100)

        elif self.config.take_profit_type == TakeProfitType.ATR:
            atr = self._calculate_atr()
            if atr:
                if self._trade_direction == OrderSide.BUY:
                    target_price = entry_price + (atr * self.config.atr_multiplier)
                else:
                    target_price = entry_price - (atr * self.config.atr_multiplier)

        elif self.config.take_profit_type == TakeProfitType.VOLATILITY:
            volatility = self._calculate_volatility()
            if volatility:
                if self._trade_direction == OrderSide.BUY:
                    target_price = entry_price * (1 + volatility * self.config.volatility_multiplier)
                else:
                    target_price = entry_price * (1 - volatility * self.config.volatility_multiplier)

        elif stop_loss and self.config.take_profit_type == TakeProfitType.RATIO:
            risk = abs(entry_price - stop_loss)
            reward = risk * self.config.risk_reward_ratio
            if self._trade_direction == OrderSide.BUY:
                target_price = entry_price + reward
            else:
                target_price = entry_price - reward

        if target_price is None:
            # Fallback to default
            if self._trade_direction == OrderSide.BUY:
                target_price = entry_price * 1.02
            else:
                target_price = entry_price * 0.98

        level = TakeProfitLevel(
            price=round_to_tick_size(target_price),
            size_percent=100.0,
            priority=1,
            type=self.config.take_profit_type
        )

        return [level]

    async def _generate_multi_levels(self, entry_price: float, stop_loss: Optional[float]) -> List[TakeProfitLevel]:
        """Generate multiple take profit levels"""
        levels = []

        # Determine base targets
        base_targets = []

        if self.config.levels:
            # Use custom levels
            for idx, level_data in enumerate(self.config.levels):
                if isinstance(level_data, dict):
                    level = TakeProfitLevel(**level_data)
                else:
                    level = level_data
                level.priority = idx + 1
                base_targets.append(level)

        else:
            # Auto-generate levels
            num_levels = self.config.number_of_levels

            # Determine min and max targets
            max_target = entry_price

            if self._trade_direction == OrderSide.BUY:
                # Calculate max target
                if self.config.take_profit_type == TakeProfitType.ATR:
                    atr = self._calculate_atr()
                    if atr:
                        max_target = entry_price + (atr * self.config.atr_multiplier * 1.5)
                elif self.config.take_profit_type == TakeProfitType.VOLATILITY:
                    volatility = self._calculate_volatility()
                    if volatility:
                        max_target = entry_price * (1 + volatility * self.config.volatility_multiplier * 2)
                elif self.config.resistance_levels:
                    # Find nearest resistance above
                    for resistance in sorted(self.config.resistance_levels):
                        if resistance > entry_price:
                            max_target = resistance
                            break

                # If still not set, use percentage
                if max_target == entry_price:
                    max_target = entry_price * 1.05

                # Generate levels between entry and max target
                step = (max_target - entry_price) / num_levels

                for i in range(1, num_levels + 1):
                    price = entry_price + (step * i)

                    # Calculate size percent based on distribution
                    size_percent = self._calculate_distribution_percent(i, num_levels)

                    levels.append(TakeProfitLevel(
                        price=round_to_tick_size(price),
                        size_percent=size_percent,
                        priority=i,
                        type=self.config.take_profit_type
                    ))

            else:  # SELL
                if self.config.take_profit_type == TakeProfitType.ATR:
                    atr = self._calculate_atr()
                    if atr:
                        max_target = entry_price - (atr * self.config.atr_multiplier * 1.5)
                elif self.config.take_profit_type == TakeProfitType.VOLATILITY:
                    volatility = self._calculate_volatility()
                    if volatility:
                        max_target = entry_price * (1 - volatility * self.config.volatility_multiplier * 2)
                elif self.config.support_levels:
                    for support in sorted(self.config.support_levels, reverse=True):
                        if support < entry_price:
                            max_target = support
                            break

                if max_target == entry_price:
                    max_target = entry_price * 0.95

                step = (entry_price - max_target) / num_levels

                for i in range(1, num_levels + 1):
                    price = entry_price - (step * i)
                    size_percent = self._calculate_distribution_percent(i, num_levels)

                    levels.append(TakeProfitLevel(
                        price=round_to_tick_size(price),
                        size_percent=size_percent,
                        priority=i,
                        type=self.config.take_profit_type
                    ))

        return levels

    async def _generate_trailing_levels(self, entry_price: float, stop_loss: Optional[float]) -> List[TakeProfitLevel]:
        """Generate trailing take profit levels"""
        levels = []

        # First level is fixed at entry + profit
        if self.config.take_profit_type == TakeProfitType.PERCENTAGE:
            target_percent = self.config.target_percent or 2.0
            if self._trade_direction == OrderSide.BUY:
                initial_target = entry_price * (1 + target_percent / 100)
            else:
                initial_target = entry_price * (1 - target_percent / 100)

            levels.append(TakeProfitLevel(
                price=round_to_tick_size(initial_target),
                size_percent=50.0,
                priority=1,
                type=TakeProfitType.PERCENTAGE,
                trailing=False
            ))

            # Second level with trailing
            if self.config.number_of_levels >= 2:
                if self._trade_direction == OrderSide.BUY:
                    second_target = initial_target * 1.01
                else:
                    second_target = initial_target * 0.99

                levels.append(TakeProfitLevel(
                    price=round_to_tick_size(second_target),
                    size_percent=50.0,
                    priority=2,
                    type=TakeProfitType.PERCENTAGE,
                    trailing=True,
                    trailing_distance=0.005
                ))

        return levels

    async def _generate_scaling_levels(self, entry_price: float, stop_loss: Optional[float]) -> List[TakeProfitLevel]:
        """Generate scaling take profit levels"""
        levels = []
        num_levels = self.config.number_of_levels

        for i in range(1, num_levels + 1):
            # Scale out more aggressively at earlier levels
            size_percent = self._calculate_distribution_percent(i, num_levels)

            if self._trade_direction == OrderSide.BUY:
                price = entry_price * (1 + (i * 0.01))
            else:
                price = entry_price * (1 - (i * 0.01))

            levels.append(TakeProfitLevel(
                price=round_to_tick_size(price),
                size_percent=size_percent,
                priority=i,
                type=TakeProfitType.PERCENTAGE
            ))

        return levels

    async def _generate_adaptive_levels(self, entry_price: float, stop_loss: Optional[float]) -> List[TakeProfitLevel]:
        """Generate adaptive take profit levels based on market conditions"""
        volatility = self._calculate_volatility()
        if volatility is None:
            volatility = 0.01

        # Adjust targets based on volatility
        volatility_factor = 1 + (volatility - 0.01) * 10

        # Use Fibonacci levels for distribution
        fib_levels = self.config.fibonacci_levels
        num_levels = min(len(fib_levels), self.config.number_of_levels)

        for i in range(num_levels):
            fib = fib_levels[i]

            if self._trade_direction == OrderSide.BUY:
                price = entry_price * (1 + (fib * volatility * volatility_factor))
            else:
                price = entry_price * (1 - (fib * volatility * volatility_factor))

            # Ensure minimum distance
            if abs(price - entry_price) < self.config.min_level_distance:
                if self._trade_direction == OrderSide.BUY:
                    price = entry_price + self.config.min_level_distance
                else:
                    price = entry_price - self.config.min_level_distance

            size_percent = self._calculate_distribution_percent(i + 1, num_levels)

            levels.append(TakeProfitLevel(
                price=round_to_tick_size(price),
                size_percent=size_percent,
                priority=i + 1,
                type=TakeProfitType.DYNAMIC
            ))

        return levels

    def _calculate_distribution_percent(self, index: int, total: int) -> float:
        """Calculate distribution percentage for a level"""
        if self.config.distribution == TakeProfitDistribution.LINEAR:
            return 100.0 / total

        elif self.config.distribution == TakeProfitDistribution.FIBONACCI:
            fib_sequence = [0.236, 0.382, 0.5, 0.618, 0.786]
            if index <= len(fib_sequence):
                weight = fib_sequence[index - 1]
            else:
                weight = 1.0 / total
            total_weight = sum(fib_sequence[:total]) if total <= len(fib_sequence) else total
            return (weight / total_weight) * 100

        elif self.config.distribution == TakeProfitDistribution.WEIGHTED:
            # Weighted towards earlier levels
            weight = 1.0 / index
            total_weight = sum(1.0 / i for i in range(1, total + 1))
            return (weight / total_weight) * 100

        elif self.config.distribution == TakeProfitDistribution.DYNAMIC:
            # Dynamic based on market conditions
            volatility = self._calculate_volatility()
            if volatility is None:
                volatility = 0.01

            # Higher volatility -> more distribution towards early levels
            weight = 1.0 / (index ** (1 + volatility))
            total_weight = sum(1.0 / (i ** (1 + volatility)) for i in range(1, total + 1))
            return (weight / total_weight) * 100

        return 100.0 / total

    def _filter_and_validate_levels(
        self,
        levels: List[TakeProfitLevel],
        entry_price: float
    ) -> List[TakeProfitLevel]:
        """Filter and validate take profit levels"""
        validated = []

        # Ensure levels are sorted by priority
        levels.sort(key=lambda x: x.priority)

        for level in levels:
            # Validate price direction
            if self._trade_direction == OrderSide.BUY:
                if level.price <= entry_price:
                    continue
            else:
                if level.price >= entry_price:
                    continue

            # Validate size percent
            level.size_percent = max(0.1, min(100, level.size_percent))

            # Apply min/max distance
            if self.config.min_target_distance:
                if abs(level.price - entry_price) < self.config.min_target_distance:
                    if self._trade_direction == OrderSide.BUY:
                        level.price = entry_price + self.config.min_target_distance
                    else:
                        level.price = entry_price - self.config.min_target_distance

            if self.config.max_target_distance:
                if abs(level.price - entry_price) > self.config.max_target_distance:
                    if self._trade_direction == OrderSide.BUY:
                        level.price = entry_price + self.config.max_target_distance
                    else:
                        level.price = entry_price - self.config.max_target_distance

            validated.append(level)

        # Ensure total size is 100%
        total_size = sum(level.size_percent for level in validated)
        if total_size > 0 and total_size != 100:
            for level in validated:
                level.size_percent = (level.size_percent / total_size) * 100

        return validated

    async def _submit_orders(self):
        """Submit take profit orders to broker"""
        if not self._broker:
            return

        for level_index, level in enumerate(self._levels):
            try:
                order_side = OrderSide.SELL if self._trade_direction == OrderSide.BUY else OrderSide.BUY
                order_size = self._position_size * (level.size_percent / 100)

                order_params = {
                    'symbol': self.config.symbol,
                    'side': order_side,
                    'quantity': order_size,
                    'time_in_force': self.config.time_in_force,
                    'client_order_id': f"{self.id}_{level_index}"
                }

                if self.config.use_limit_orders:
                    order_params['order_type'] = OrderType.LIMIT
                    order_params['price'] = level.price
                    if self.config.limit_offset is not None:
                        if order_side == OrderSide.SELL:
                            order_params['price'] = level.price - self.config.limit_offset
                        else:
                            order_params['price'] = level.price + self.config.limit_offset
                else:
                    order_params['order_type'] = OrderType.MARKET

                # Submit order
                result = await self._broker.place_order(**order_params)
                self._order_ids[level_index] = result.get('order_id')

                logger.debug(f"Submitted order for level {level_index} at {level.price}")

            except Exception as e:
                logger.error(f"Failed to submit order for level {level_index}: {e}")
                self._order_queue.append({
                    'level_index': level_index,
                    'level': level,
                    'retry_count': 0
                })

    async def _check_and_execute_levels(self, current_price: float) -> List[float]:
        """Check and execute take profit levels"""
        executed = []

        for level_index, level in enumerate(self._levels):
            if level_index in self._executed_levels:
                continue

            # Check if price reached level
            reached = False
            if self._trade_direction == OrderSide.BUY:
                reached = current_price >= level.price
            else:
                reached = current_price <= level.price

            if reached:
                # Execute level
                success = await self._execute_level(level_index, level, current_price)
                if success:
                    executed.append(level.price)
                    self._executed_levels.append(level_index)

                    # Update remaining size
                    self._remaining_size -= self._position_size * (level.size_percent / 100)

                    # Update metrics
                    self._metrics.achieved_levels.append(level.price)
                    self._metrics.achieved_percent += level.size_percent
                    self._metrics.partial_fills += 1

        # Check if all levels executed
        if len(self._executed_levels) == len(self._levels):
            self._state = 'EXECUTED'
            self._metrics.full_fills = 1
            self._metrics.time_to_full_target = datetime.utcnow()
            logger.info(f"Take profit {self.id} fully executed")

        return executed

    async def _execute_level(self, level_index: int, level: TakeProfitLevel, current_price: float) -> bool:
        """Execute a take profit level"""
        if not self._broker:
            return False

        try:
            order_id = self._order_ids.get(level_index)
            if order_id:
                # Check order status
                status = await self._broker.get_order_status(order_id)

                if status.get('status') == 'FILLED':
                    # Calculate profit
                    profit = self._calculate_level_profit(level, current_price)
                    self._metrics.total_profit += profit
                    self._metrics.total_profit_percent += profit / self._position_size * 100

                    return True

                elif status.get('status') in ['PENDING', 'WORKING']:
                    # Order is working, wait for fill
                    await asyncio.sleep(0.5)
                    return await self._execute_level(level_index, level, current_price)

            # Place new market order
            order_side = OrderSide.SELL if self._trade_direction == OrderSide.BUY else OrderSide.BUY
            order_size = self._position_size * (level.size_percent / 100)

            result = await self._broker.place_order(
                symbol=self.config.symbol,
                side=order_side,
                order_type=OrderType.MARKET,
                quantity=order_size,
                time_in_force=TimeInForce.IOC
            )

            if result.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                profit = self._calculate_level_profit(level, current_price)
                self._metrics.total_profit += profit
                self._metrics.total_profit_percent += profit / self._position_size * 100

                self._order_ids[level_index] = result.get('order_id')
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to execute level {level_index}: {e}")
            return False

    def _calculate_level_profit(self, level: TakeProfitLevel, current_price: float) -> float:
        """Calculate profit for a level"""
        if self._trade_direction == OrderSide.BUY:
            price_diff = current_price - self._entry_price
        else:
            price_diff = self._entry_price - current_price

        size = self._position_size * (level.size_percent / 100)
        return price_diff * size

    async def _update_trailing_levels(self, current_price: float):
        """Update trailing take profit levels"""
        if not self.config.enable_trailing:
            return

        for level_index, level in enumerate(self._levels):
            if level_index in self._executed_levels:
                continue

            if not level.trailing:
                continue

            # Check if activation condition met
            if self.config.trailing_activation:
                if self._trade_direction == OrderSide.BUY:
                    if current_price < self.config.trailing_activation:
                        continue
                else:
                    if current_price > self.config.trailing_activation:
                        continue

            # Update trailing level
            if self._trade_direction == OrderSide.BUY:
                new_price = current_price * (1 - self.config.trailing_step)
                if new_price > level.price:
                    level.price = round_to_tick_size(new_price)
                    await self._update_order_price(level_index, level.price)
            else:
                new_price = current_price * (1 + self.config.trailing_step)
                if new_price < level.price:
                    level.price = round_to_tick_size(new_price)
                    await self._update_order_price(level_index, level.price)

    async def _update_order_price(self, level_index: int, new_price: float):
        """Update order price for a level"""
        order_id = self._order_ids.get(level_index)
        if not order_id:
            return

        try:
            await self._broker.update_order(
                order_id=order_id,
                price=new_price
            )
            logger.debug(f"Updated order {order_id} to price {new_price}")

        except Exception as e:
            logger.error(f"Failed to update order {order_id}: {e}")

    def _calculate_atr(self) -> Optional[float]:
        """Calculate ATR from price history"""
        if len(self._price_history) < self.config.atr_period + 1:
            return None

        true_ranges = []
        for i in range(1, self.config.atr_period + 1):
            high = max(self._price_history[-i], self._price_history[-i-1])
            low = min(self._price_history[-i], self._price_history[-i-1])
            true_range = high - low
            true_ranges.append(true_range)

        return sum(true_ranges) / len(true_ranges)

    def _calculate_volatility(self) -> Optional[float]:
        """Calculate volatility from price history"""
        if len(self._price_history) < self.config.volatility_window:
            return None

        returns = []
        for i in range(1, self.config.volatility_window):
            if self._price_history[i-1] != 0:
                returns.append((self._price_history[i] - self._price_history[i-1]) / self._price_history[i-1])

        if not returns:
            return None

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return variance ** 0.5

    async def register_price_feed(self, callback: Callable[[float], Awaitable[None]]):
        """
        Register a price feed callback for automatic updates.

        Args:
            callback: Async callback function that receives price updates
        """
        self._price_callback = callback

    async def start_price_monitoring(self, websocket_client: Optional[Any] = None):
        """
        Start monitoring price via WebSocket.

        Args:
            websocket_client: Optional WebSocket client for price data
        """
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
        """Handle price updates from WebSocket"""
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
        """Convert smart take profit to dictionary"""
        return {
            'id': self.id,
            'state': self._state,
            'config': self.config.model_dump(),
            'metrics': self._metrics.model_dump(),
            'entry_price': self._entry_price,
            'current_price': self._current_price,
            'direction': self._trade_direction.value if self._trade_direction else None,
            'position_size': self._position_size,
            'remaining_size': self._remaining_size,
            'levels': [level.model_dump() for level in self._levels],
            'executed_levels': self._executed_levels,
            'order_ids': self._order_ids
        }

    @classmethod
    async def from_dict(
        cls,
        data: Dict[str, Any],
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ) -> 'SmartTakeProfit':
        """Create smart take profit from dictionary"""
        config = SmartTakeProfitConfig(**data.get('config', {}))
        take_profit = cls(config=config, broker=broker, order_manager=order_manager)

        # Restore state
        take_profit._state = data.get('state', 'INACTIVE')
        take_profit._entry_price = data.get('entry_price')
        take_profit._current_price = data.get('current_price')
        take_profit._position_size = data.get('position_size')
        take_profit._remaining_size = data.get('remaining_size')
        take_profit._executed_levels = data.get('executed_levels', [])

        if data.get('direction'):
            take_profit._trade_direction = OrderSide(data.get('direction'))

        # Restore levels
        if data.get('levels'):
            take_profit._levels = [TakeProfitLevel(**level) for level in data.get('levels')]

        # Restore order IDs
        if data.get('order_ids'):
            take_profit._order_ids = {int(k): v for k, v in data.get('order_ids').items()}

        # Restore metrics
        if data.get('metrics'):
            take_profit._metrics = TakeProfitMetrics(**data.get('metrics'))

        return take_profit

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cancel()
        await self.stop_price_monitoring()

