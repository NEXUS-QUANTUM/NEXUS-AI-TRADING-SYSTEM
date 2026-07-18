"""
NEXUS AI TRADING SYSTEM - Smart Stop Order Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/smart_stop.py
Version: 1.0.0
Description: Advanced smart stop loss implementation with full API integration
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
    calculate_atr,
    calculate_support_resistance
)
from shared.constants.trading_constants import (
    MIN_STOP_DISTANCE,
    DEFAULT_STOP_PERCENTAGE,
    MAX_STOP_ORDERS
)
from shared.interfaces.broker import BrokerInterface
from trading.smart_orders.base_order import SmartOrder, SmartOrderConfig
from trading.smart_orders.order_manager import OrderManager

logger = logging.getLogger(__name__)


class SmartStopType(str, Enum):
    """Types of smart stop mechanisms"""
    FIXED = "fixed"                  # Fixed price stop
    PERCENTAGE = "percentage"        # Percentage-based stop
    ATR = "atr"                      # ATR-based stop
    VOLATILITY = "volatility"        # Volatility-based stop
    SUPPORT = "support"              # Support level stop
    RESISTANCE = "resistance"        # Resistance level stop
    DYNAMIC = "dynamic"              # Dynamic calculation
    ADAPTIVE = "adaptive"            # Adaptive to market conditions
    CHANDELIER = "chandelier"        # Chandelier exit stop
    VOLUME = "volume"                # Volume-based stop


class SmartStopMode(str, Enum):
    """Smart stop modes"""
    STANDARD = "standard"            # Standard stop loss
    TRAILING = "trailing"            # Trailing stop loss
    STEPPED = "stepped"              # Step-based adjustment
    ACCELERATED = "accelerated"      # Accelerated trailing
    DECELERATED = "decelerated"      # Decelerated trailing
    BREAKEVEN = "breakeven"          # Breakeven stop
    DYNAMIC = "dynamic"              # Dynamic adjustment


class SmartStopLevel(BaseModel):
    """Individual stop level configuration"""
    price: float = Field(..., description="Stop price")
    size_percent: float = Field(100.0, description="Percentage of position to stop")
    priority: int = Field(1, description="Priority order")
    type: SmartStopType = Field(default=SmartStopType.FIXED)
    trailing: bool = Field(False, description="Whether this level is trailing")
    trailing_distance: Optional[float] = Field(None, description="Trailing distance for this level")
    description: Optional[str] = Field(None, description="Description of this level")


class SmartStopMetrics(BaseModel):
    """Metrics for smart stop performance analysis"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    entry_price: Optional[float] = Field(None, description="Entry price")
    current_price: Optional[float] = Field(None, description="Current market price")
    initial_stop: Optional[float] = Field(None, description="Initial stop price")
    current_stop: Optional[float] = Field(None, description="Current stop price")
    
    highest_price: Optional[float] = Field(None, description="Highest price reached")
    lowest_price: Optional[float] = Field(None, description="Lowest price reached")
    
    stop_moves: int = Field(0, description="Number of stop adjustments")
    stop_distance: Optional[float] = Field(None, description="Current distance from stop")
    stop_percent: Optional[float] = Field(None, description="Current stop percentage")
    
    protected_profit: float = Field(0.0, description="Profit protected by stop")
    realized_profit: float = Field(0.0, description="Realized profit from stop")
    unrealized_profit: float = Field(0.0, description="Unrealized profit")
    
    max_favorable_excursion: float = Field(0.0, description="Maximum favorable price movement")
    max_adverse_excursion: float = Field(0.0, description="Maximum adverse price movement")
    
    time_to_breakeven: Optional[datetime] = Field(None, description="Time to reach breakeven")
    time_to_stop: Optional[datetime] = Field(None, description="Time when stop was hit")


class SmartStopConfig(SmartOrderConfig):
    """Configuration for smart stop order"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    stop_type: SmartStopType = Field(default=SmartStopType.PERCENTAGE)
    mode: SmartStopMode = Field(default=SmartStopMode.STANDARD)
    
    # Fixed/Percentage settings
    stop_price: Optional[float] = Field(None, description="Fixed stop price")
    stop_percent: Optional[float] = Field(None, description="Stop percentage (1.0 = 1%)")
    
    # ATR settings
    atr_multiplier: float = Field(2.0, description="ATR multiplier for stop distance")
    atr_period: int = Field(14, description="ATR calculation period")
    
    # Volatility settings
    volatility_multiplier: float = Field(2.0, description="Volatility multiplier")
    volatility_window: int = Field(20, description="Volatility calculation window")
    
    # Chandelier settings
    chandelier_avg_period: int = Field(22, description="Chandelier average period")
    chandelier_multiplier: float = Field(3.0, description="Chandelier multiplier")
    
    # Volume settings
    volume_threshold: float = Field(1.5, description="Volume threshold multiplier")
    volume_window: int = Field(20, description="Volume window")
    
    # Dynamic settings
    min_stop_distance: Optional[float] = Field(None, description="Minimum stop distance")
    max_stop_distance: Optional[float] = Field(None, description="Maximum stop distance")
    adaptation_speed: float = Field(0.5, description="Adaptation speed (0-1)")
    
    # Breakeven settings
    breakeven_after_percent: Optional[float] = Field(None, description="Profit % to trigger breakeven")
    breakeven_buffer: float = Field(0.001, description="Breakeven buffer (0.1%)")
    
    # Trailing settings
    trailing_activation_percent: Optional[float] = Field(None, description="Profit % to start trailing")
    trailing_step: float = Field(0.01, description="Trailing step size")
    trailing_interval: float = Field(0.01, description="Trailing interval")
    
    # Stepped settings
    step_size: Optional[float] = Field(None, description="Step size for stepped mode")
    step_interval: float = Field(0.01, description="Step interval")
    
    # Accelerated/Decelerated settings
    acceleration_factor: float = Field(0.1, description="Acceleration factor")
    deceleration_factor: float = Field(0.1, description="Deceleration factor")
    
    # Multi-stop settings
    levels: List[SmartStopLevel] = Field(default_factory=list, description="Stop levels")
    use_multiple_stops: bool = Field(False, description="Use multiple stop levels")
    stop_distribution: List[float] = Field(default_factory=list, description="Stop distribution percentages")
    
    # Order settings
    order_size: float = Field(..., description="Size of the order")
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    expire_after: Optional[timedelta] = Field(None, description="Expiration time")
    max_slippage: float = Field(0.01, description="Maximum allowed slippage")
    use_market_orders: bool = Field(False, description="Use market orders instead of limit")
    limit_offset: Optional[float] = Field(None, description="Offset for limit orders")
    
    # Risk settings
    max_risk_percent: Optional[float] = Field(None, description="Maximum risk percentage")
    max_loss_amount: Optional[float] = Field(None, description="Maximum loss amount")
    min_risk_reward: Optional[float] = Field(None, description="Minimum risk-reward ratio")
    
    # Smart features
    dynamic_adjustment: bool = Field(True, description="Enable dynamic adjustment")
    use_support_resistance: bool = Field(False, description="Use support/resistance levels")
    adjust_on_news: bool = Field(False, description="Adjust on news events")
    volatility_adjustment: bool = Field(True, description="Enable volatility adjustment")

    @validator('stop_percent')
    def validate_stop_percent(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Stop percentage must be positive")
        return v

    @validator('atr_multiplier')
    def validate_atr(cls, v):
        if v <= 0:
            raise ValueError("ATR multiplier must be positive")
        return v

    @validator('volatility_multiplier')
    def validate_volatility(cls, v):
        if v <= 0:
            raise ValueError("Volatility multiplier must be positive")
        return v

    @validator('adaptation_speed')
    def validate_adaptation(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Adaptation speed must be between 0 and 1")
        return v

    @validator('acceleration_factor')
    def validate_acceleration(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Acceleration factor must be between 0 and 1")
        return v


class StopExecution(BaseModel):
    """Execution result for stop order"""
    level_index: int
    stop_price: float
    executed_price: float
    executed_size: float
    realized_profit: float
    status: OrderStatus
    timestamp: datetime
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class SmartStop(SmartOrder):
    """
    Advanced smart stop loss implementation with full API integration.
    
    Supports multiple stop mechanisms:
    - Fixed price stops
    - Percentage-based stops
    - ATR-based stops
    - Volatility-based stops
    - Support/Resistance levels
    - Chandelier exit
    - Volume-based stops
    
    Features:
    - Multiple stop levels with distribution
    - Trailing stop with acceleration/deceleration
    - Breakeven stop management
    - Dynamic adaptation to market conditions
    - Full broker API integration
    - Performance metrics tracking
    - Real-time price monitoring
    """

    def __init__(
        self,
        config: SmartStopConfig,
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ):
        """
        Initialize smart stop order.

        Args:
            config: Stop configuration
            broker: Optional broker interface for execution
            order_manager: Optional order manager for coordination
        """
        super().__init__(config=config, broker=broker, order_manager=order_manager)
        self.config = config
        self._metrics = SmartStopMetrics()
        self._state = 'INACTIVE'
        self._current_price: Optional[float] = None
        self._entry_price: Optional[float] = None
        self._trade_direction: Optional[OrderSide] = None
        self._position_size: Optional[float] = None
        self._remaining_size: Optional[float] = None
        self._current_stop: Optional[float] = None
        self._levels: List[SmartStopLevel] = []
        self._order_ids: Dict[int, str] = {}
        self._executed_levels: List[int] = []
        self._breakeven_triggered: bool = False
        self._trailing_started: bool = False
        self._subscription_id: Optional[str] = None

        # Price history
        self._price_history: List[float] = []
        self._volume_history: List[float] = []
        self._timestamp_history: List[datetime] = []
        self._max_history_length = 1000

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(f"Initialized SmartStop with ID: {self.id}")

    async def activate(
        self,
        price: float,
        direction: OrderSide,
        size: float,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Activate the smart stop order.

        Args:
            price: Entry price
            direction: Trade direction (BUY/SELL)
            size: Position size
            take_profit: Optional take profit price

        Returns:
            bool: True if activated successfully
        """
        async with self._lock:
            if self._state in ['ACTIVE', 'EXECUTED']:
                logger.warning(f"Smart stop {self.id} already active or executed")
                return False

            self._entry_price = price
            self._trade_direction = direction
            self._position_size = size
            self._remaining_size = size

            # Generate stop levels
            self._levels = await self._generate_stop_levels(price, take_profit)

            if not self._levels:
                logger.error(f"No stop levels generated for {self.id}")
                return False

            # Set initial stop
            self._current_stop = self._levels[0].price

            # Set metrics
            self._metrics.entry_price = price
            self._metrics.current_price = price
            self._metrics.initial_stop = self._current_stop
            self._metrics.current_stop = self._current_stop
            self._metrics.highest_price = price
            self._metrics.lowest_price = price
            self._metrics.stop_distance = abs(price - self._current_stop)
            self._metrics.stop_percent = self._metrics.stop_distance / price * 100

            self._state = 'ACTIVE'
            self._current_price = price

            # Submit orders
            if self._broker:
                await self._submit_stop_orders()

            logger.info(
                f"Smart stop {self.id} activated at price {price}, "
                f"stop: {self._current_stop}, direction: {direction.value}"
            )

            return True

    async def update_price(self, new_price: float, timestamp: Optional[datetime] = None) -> Optional[float]:
        """
        Update current price and adjust stop if needed.

        Args:
            new_price: Current market price
            timestamp: Optional timestamp of price update

        Returns:
            Optional[float]: New stop price if updated, None otherwise
        """
        async with self._lock:
            if self._state != 'ACTIVE':
                return None

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
                self._calculate_profit_percent(new_price)
            )
            self._metrics.max_adverse_excursion = min(
                self._metrics.max_adverse_excursion,
                self._calculate_profit_percent(new_price)
            )

            # Check for breakeven
            if not self._breakeven_triggered and self.config.breakeven_after_percent:
                if self._calculate_profit_percent(new_price) >= self.config.breakeven_after_percent:
                    await self._trigger_breakeven()
                    self._breakeven_triggered = True

            # Check for trailing activation
            if not self._trailing_started and self.config.trailing_activation_percent:
                if self._calculate_profit_percent(new_price) >= self.config.trailing_activation_percent:
                    self._trailing_started = True

            # Calculate new stop
            new_stop = await self._calculate_adjusted_stop(new_price)

            if new_stop != self._current_stop:
                self._current_stop = new_stop
                self._metrics.current_stop = new_stop
                self._metrics.stop_moves += 1
                self._metrics.stop_distance = abs(new_price - new_stop)
                self._metrics.stop_percent = self._metrics.stop_distance / new_price * 100

                # Update stop orders
                await self._update_stop_orders(new_stop)

                logger.debug(
                    f"Smart stop {self.id} updated: stop={new_stop}, "
                    f"price={new_price}, profit={self._calculate_profit_percent(new_price):.2f}%"
                )

                return new_stop

            return None

    async def check_trigger(self, price: Optional[float] = None) -> bool:
        """
        Check if the stop should be triggered.

        Args:
            price: Current price to check

        Returns:
            bool: True if triggered
        """
        async with self._lock:
            if self._state != 'ACTIVE':
                return False

            check_price = price or self._current_price
            if check_price is None:
                return False

            triggered = False
            if self._trade_direction == OrderSide.BUY:
                if check_price <= self._current_stop:
                    triggered = True
            else:  # SELL
                if check_price >= self._current_stop:
                    triggered = True

            if triggered:
                self._state = 'TRIGGERED'
                self._metrics.time_to_stop = datetime.utcnow()
                await self._execute_stop_orders()
                logger.info(f"Smart stop {self.id} triggered at price {check_price}")

            return triggered

    async def cancel(self) -> bool:
        """
        Cancel the smart stop orders.

        Returns:
            bool: True if cancelled successfully
        """
        async with self._lock:
            if self._state == 'CANCELLED':
                return False

            self._state = 'CANCELLED'

            for level_index, order_id in self._order_ids.items():
                try:
                    await self._broker.cancel_order(order_id)
                    logger.debug(f"Cancelled order {order_id} for level {level_index}")
                except Exception as e:
                    logger.error(f"Failed to cancel order {order_id}: {e}")

            self._order_ids.clear()
            logger.info(f"Smart stop {self.id} cancelled")

            return True

    async def get_metrics(self) -> SmartStopMetrics:
        """Get current stop metrics"""
        async with self._lock:
            metrics = self._metrics.model_copy()
            metrics.stop_distance = self._metrics.stop_distance
            metrics.stop_percent = self._metrics.stop_percent
            return metrics

    def get_state(self) -> str:
        """Get current state"""
        return self._state

    def get_stop_price(self) -> Optional[float]:
        """Get current stop price"""
        return self._current_stop

    def get_current_price(self) -> Optional[float]:
        """Get current price"""
        return self._current_price

    def get_stop_distance(self) -> Optional[float]:
        """Get distance from stop"""
        if self._current_price is None or self._current_stop is None:
            return None
        return abs(self._current_price - self._current_stop)

    def get_profit_protected(self) -> float:
        """Get protected profit"""
        return self._metrics.protected_profit

    def get_risk_amount(self) -> Optional[float]:
        """Get current risk amount"""
        if self._entry_price is None or self._current_stop is None:
            return None
        risk = abs(self._entry_price - self._current_stop) * self._remaining_size
        return risk

    async def _generate_stop_levels(self, entry_price: float, take_profit: Optional[float]) -> List[SmartStopLevel]:
        """Generate stop levels based on configuration"""
        levels = []

        if self.config.use_multiple_stops and self.config.levels:
            # Use custom levels
            for idx, level_data in enumerate(self.config.levels):
                if isinstance(level_data, dict):
                    level = SmartStopLevel(**level_data)
                else:
                    level = level_data
                level.priority = idx + 1
                levels.append(level)
            return levels

        # Generate single stop level
        stop_price = await self._calculate_stop_price(entry_price, take_profit)

        level = SmartStopLevel(
            price=round_to_tick_size(stop_price),
            size_percent=100.0,
            priority=1,
            type=self.config.stop_type,
            trailing=self.config.mode in [SmartStopMode.TRAILING, SmartStopMode.ACCELERATED, SmartStopMode.DECELERATED]
        )

        # Add additional levels if using distribution
        if self.config.use_multiple_stops and self.config.stop_distribution:
            total_so_far = 0
            for idx, dist_percent in enumerate(self.config.stop_distribution):
                if idx == 0:
                    continue  # First level already defined
                stop_multiplier = 1 + (idx * 0.5)  # Widen stop for additional levels
                if self._trade_direction == OrderSide.BUY:
                    price = entry_price - (abs(entry_price - stop_price) * stop_multiplier)
                else:
                    price = entry_price + (abs(entry_price - stop_price) * stop_multiplier)

                levels.append(SmartStopLevel(
                    price=round_to_tick_size(price),
                    size_percent=dist_percent,
                    priority=idx + 1,
                    type=self.config.stop_type,
                    trailing=False
                ))

        return levels

    async def _calculate_stop_price(self, entry_price: float, take_profit: Optional[float]) -> float:
        """Calculate stop price based on configuration"""
        if self.config.stop_price:
            return self.config.stop_price

        if self.config.stop_percent:
            if self._trade_direction == OrderSide.BUY:
                return entry_price * (1 - self.config.stop_percent / 100)
            else:
                return entry_price * (1 + self.config.stop_percent / 100)

        if self.config.stop_type == SmartStopType.ATR:
            atr = self._calculate_atr()
            if atr:
                if self._trade_direction == OrderSide.BUY:
                    return entry_price - (atr * self.config.atr_multiplier)
                else:
                    return entry_price + (atr * self.config.atr_multiplier)

        if self.config.stop_type == SmartStopType.VOLATILITY:
            volatility = self._calculate_volatility()
            if volatility:
                if self._trade_direction == OrderSide.BUY:
                    return entry_price * (1 - volatility * self.config.volatility_multiplier)
                else:
                    return entry_price * (1 + volatility * self.config.volatility_multiplier)

        if self.config.stop_type == SmartStopType.SUPPORT:
            support_levels = await self._find_support_resistance(entry_price, 'support')
            if support_levels:
                if self._trade_direction == OrderSide.BUY:
                    return max(support_levels[0], entry_price - (entry_price * 0.05))
                else:
                    return support_levels[0]

        if self.config.stop_type == SmartStopType.RESISTANCE:
            resistance_levels = await self._find_support_resistance(entry_price, 'resistance')
            if resistance_levels:
                if self._trade_direction == OrderSide.BUY:
                    return resistance_levels[0]
                else:
                    return min(resistance_levels[0], entry_price + (entry_price * 0.05))

        if self.config.stop_type == SmartStopType.CHANDELIER:
            return await self._calculate_chandelier_stop(entry_price)

        if self.config.stop_type == SmartStopType.VOLUME:
            return await self._calculate_volume_stop(entry_price)

        if self.config.stop_type == SmartStopType.ADAPTIVE:
            return await self._calculate_adaptive_stop(entry_price)

        if self.config.stop_type == SmartStopType.DYNAMIC:
            return await self._calculate_dynamic_stop(entry_price)

        # Fallback to percentage
        if self._trade_direction == OrderSide.BUY:
            return entry_price * (1 - DEFAULT_STOP_PERCENTAGE)
        else:
            return entry_price * (1 + DEFAULT_STOP_PERCENTAGE)

    async def _calculate_adjusted_stop(self, current_price: float) -> float:
        """Calculate adjusted stop based on mode"""
        if self.config.mode == SmartStopMode.STANDARD:
            return self._current_stop or current_price

        elif self.config.mode == SmartStopMode.TRAILING:
            return await self._calculate_trailing_stop(current_price)

        elif self.config.mode == SmartStopMode.STEPPED:
            return await self._calculate_stepped_stop(current_price)

        elif self.config.mode == SmartStopMode.ACCELERATED:
            return await self._calculate_accelerated_stop(current_price)

        elif self.config.mode == SmartStopMode.DECELERATED:
            return await self._calculate_decelerated_stop(current_price)

        elif self.config.mode == SmartStopMode.BREAKEVEN:
            return await self._calculate_breakeven_stop(current_price)

        elif self.config.mode == SmartStopMode.DYNAMIC:
            return await self._calculate_dynamic_stop(current_price)

        return self._current_stop or current_price

    async def _calculate_trailing_stop(self, current_price: float) -> float:
        """Calculate trailing stop"""
        if not self._trailing_started:
            return self._current_stop or current_price

        if self._trade_direction == OrderSide.BUY:
            # For long positions, trail stop up
            new_stop = current_price * (1 - self.config.trailing_step)
            return max(new_stop, self._current_stop or current_price)
        else:
            # For short positions, trail stop down
            new_stop = current_price * (1 + self.config.trailing_step)
            return min(new_stop, self._current_stop or current_price)

    async def _calculate_stepped_stop(self, current_price: float) -> float:
        """Calculate stepped trailing stop"""
        if not self._trailing_started:
            return self._current_stop or current_price

        step_size = self.config.step_size or 0.01

        if self._trade_direction == OrderSide.BUY:
            # Only move in steps
            stop_step = self._current_stop or current_price
            price_threshold = stop_step + step_size
            if current_price >= price_threshold:
                return stop_step + step_size
            return stop_step
        else:
            stop_step = self._current_stop or current_price
            price_threshold = stop_step - step_size
            if current_price <= price_threshold:
                return stop_step - step_size
            return stop_step

    async def _calculate_accelerated_stop(self, current_price: float) -> float:
        """Calculate accelerated trailing stop"""
        if not self._trailing_started or self._entry_price is None:
            return self._current_stop or current_price

        profit_percent = self._calculate_profit_percent(current_price)

        if self._trade_direction == OrderSide.BUY:
            base_stop = current_price * (1 - self.config.trailing_step)
            acceleration = 1 + (profit_percent / 100) * self.config.acceleration_factor
            stop_distance = abs(current_price - base_stop) * acceleration
            new_stop = current_price - min(stop_distance, current_price * 0.1)
            return max(new_stop, self._current_stop or current_price)
        else:
            base_stop = current_price * (1 + self.config.trailing_step)
            acceleration = 1 + (profit_percent / 100) * self.config.acceleration_factor
            stop_distance = abs(current_price - base_stop) * acceleration
            new_stop = current_price + min(stop_distance, current_price * 0.1)
            return min(new_stop, self._current_stop or current_price)

    async def _calculate_decelerated_stop(self, current_price: float) -> float:
        """Calculate decelerated trailing stop"""
        if not self._trailing_started or self._entry_price is None:
            return self._current_stop or current_price

        profit_percent = self._calculate_profit_percent(current_price)

        if self._trade_direction == OrderSide.BUY:
            base_stop = current_price * (1 - self.config.trailing_step)
            deceleration = 1 - (profit_percent / 100) * self.config.deceleration_factor
            deceleration = max(0.5, deceleration)
            stop_distance = abs(current_price - base_stop) * deceleration
            stop_distance = max(stop_distance, MIN_STOP_DISTANCE)
            new_stop = current_price - stop_distance
            return max(new_stop, self._current_stop or current_price)
        else:
            base_stop = current_price * (1 + self.config.trailing_step)
            deceleration = 1 - (profit_percent / 100) * self.config.deceleration_factor
            deceleration = max(0.5, deceleration)
            stop_distance = abs(current_price - base_stop) * deceleration
            stop_distance = max(stop_distance, MIN_STOP_DISTANCE)
            new_stop = current_price + stop_distance
            return min(new_stop, self._current_stop or current_price)

    async def _calculate_breakeven_stop(self, current_price: float) -> float:
        """Calculate breakeven stop"""
        if self._entry_price is None:
            return self._current_stop or current_price

        if not self._breakeven_triggered:
            return self._current_stop or current_price

        buffer = self.config.breakeven_buffer
        if self._trade_direction == OrderSide.BUY:
            return self._entry_price + buffer
        else:
            return self._entry_price - buffer

    async def _calculate_dynamic_stop(self, current_price: float) -> float:
        """Calculate dynamic stop based on market conditions"""
        volatility = self._calculate_volatility()
        if volatility is None:
            return self._current_stop or current_price

        # Adjust stop based on volatility
        base_distance = abs(current_price - (self._current_stop or current_price))
        volatility_adjustment = 1 + (volatility - 0.01) * 10 * self.config.adaptation_speed
        new_distance = base_distance * volatility_adjustment

        # Apply min/max limits
        if self.config.min_stop_distance:
            new_distance = max(new_distance, self.config.min_stop_distance)
        if self.config.max_stop_distance:
            new_distance = min(new_distance, self.config.max_stop_distance)

        if self._trade_direction == OrderSide.BUY:
            new_stop = current_price - new_distance
            return max(new_stop, self._current_stop or current_price)
        else:
            new_stop = current_price + new_distance
            return min(new_stop, self._current_stop or current_price)

    async def _calculate_chandelier_stop(self, entry_price: float) -> float:
        """Calculate chandelier exit stop"""
        if len(self._price_history) < self.config.chandelier_avg_period:
            return entry_price * (1 - 0.02) if self._trade_direction == OrderSide.BUY else entry_price * (1 + 0.02)

        # Calculate highest high and lowest low
        highs = self._price_history[-self.config.chandelier_avg_period:]
        lows = self._price_history[-self.config.chandelier_avg_period:]

        atr = self._calculate_atr()
        if atr is None:
            atr = entry_price * 0.01

        if self._trade_direction == OrderSide.BUY:
            highest_high = max(highs)
            return highest_high - (atr * self.config.chandelier_multiplier)
        else:
            lowest_low = min(lows)
            return lowest_low + (atr * self.config.chandelier_multiplier)

    async def _calculate_volume_stop(self, entry_price: float) -> float:
        """Calculate volume-based stop"""
        if len(self._volume_history) < self.config.volume_window:
            return entry_price * (1 - 0.02) if self._trade_direction == OrderSide.BUY else entry_price * (1 + 0.02)

        avg_volume = sum(self._volume_history[-self.config.volume_window:]) / self.config.volume_window
        current_volume = self._volume_history[-1] if self._volume_history else avg_volume

        # Higher volume = tighter stop
        volume_ratio = current_volume / avg_volume
        stop_multiplier = 1 / (1 + (volume_ratio - 1) * 0.5)

        if self._trade_direction == OrderSide.BUY:
            return entry_price * (1 - 0.02 * stop_multiplier)
        else:
            return entry_price * (1 + 0.02 * stop_multiplier)

    async def _calculate_adaptive_stop(self, entry_price: float) -> float:
        """Calculate adaptive stop"""
        volatility = self._calculate_volatility()
        if volatility is None:
            volatility = 0.01

        # Use ATR with adaptive multiplier
        atr = self._calculate_atr()
        if atr is None:
            atr = entry_price * 0.01

        # Adjust multiplier based on market conditions
        base_multiplier = self.config.atr_multiplier
        volatility_factor = 1 + (volatility - 0.01) * 5
        adaptive_multiplier = base_multiplier * volatility_factor

        if self._trade_direction == OrderSide.BUY:
            return entry_price - (atr * adaptive_multiplier)
        else:
            return entry_price + (atr * adaptive_multiplier)

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

    def _calculate_profit_percent(self, current_price: float) -> float:
        """Calculate profit percentage"""
        if self._entry_price is None or self._entry_price == 0:
            return 0

        if self._trade_direction == OrderSide.BUY:
            return (current_price - self._entry_price) / self._entry_price * 100
        else:
            return (self._entry_price - current_price) / self._entry_price * 100

    async def _find_support_resistance(self, price: float, level_type: str) -> List[float]:
        """Find support/resistance levels"""
        # Simplified implementation - would use actual analysis in production
        levels = []
        if level_type == 'support':
            # Look for support below current price
            for i in range(1, 5):
                levels.append(price * (1 - i * 0.01))
        else:
            # Look for resistance above current price
            for i in range(1, 5):
                levels.append(price * (1 + i * 0.01))
        return levels

    async def _trigger_breakeven(self):
        """Trigger breakeven stop"""
        if self._entry_price is None:
            return

        breakeven_stop = self._entry_price
        if self._trade_direction == OrderSide.BUY:
            breakeven_stop += self.config.breakeven_buffer
        else:
            breakeven_stop -= self.config.breakeven_buffer

        self._current_stop = breakeven_stop
        self._metrics.current_stop = breakeven_stop
        self._metrics.stop_moves += 1
        self._metrics.time_to_breakeven = datetime.utcnow()

        await self._update_stop_orders(breakeven_stop)

        logger.info(f"Smart stop {self.id} moved to breakeven at {breakeven_stop}")

    async def _submit_stop_orders(self):
        """Submit stop orders to broker"""
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

                if self.config.use_market_orders:
                    order_params['order_type'] = OrderType.STOP_MARKET
                    order_params['stop_price'] = level.price
                else:
                    order_params['order_type'] = OrderType.STOP_LIMIT
                    order_params['stop_price'] = level.price
                    if self.config.limit_offset is not None:
                        if order_side == OrderSide.SELL:
                            order_params['limit_price'] = level.price - self.config.limit_offset
                        else:
                            order_params['limit_price'] = level.price + self.config.limit_offset

                result = await self._broker.place_order(**order_params)
                self._order_ids[level_index] = result.get('order_id')

                logger.debug(f"Submitted stop order for level {level_index} at {level.price}")

            except Exception as e:
                logger.error(f"Failed to submit stop order for level {level_index}: {e}")

    async def _update_stop_orders(self, new_stop: float):
        """Update stop orders with new stop price"""
        if not self._broker:
            return

        for level_index, level in enumerate(self._levels):
            if level_index in self._executed_levels:
                continue

            order_id = self._order_ids.get(level_index)
            if not order_id:
                continue

            # Calculate new price based on distribution
            price_diff = new_stop - self._levels[0].price
            new_price = level.price + price_diff

            try:
                await self._broker.update_order(
                    order_id=order_id,
                    stop_price=new_price
                )
                level.price = new_price
                logger.debug(f"Updated stop order {order_id} to {new_price}")

            except Exception as e:
                logger.error(f"Failed to update stop order {order_id}: {e}")

    async def _execute_stop_orders(self):
        """Execute stop orders when triggered"""
        if not self._broker:
            return

        for level_index, level in enumerate(self._levels):
            if level_index in self._executed_levels:
                continue

            order_id = self._order_ids.get(level_index)
            if order_id:
                try:
                    status = await self._broker.get_order_status(order_id)
                    if status.get('status') == 'FILLED':
                        self._executed_levels.append(level_index)
                        self._remaining_size -= self._position_size * (level.size_percent / 100)

                        # Calculate realized profit
                        exec_price = status.get('price', level.price)
                        profit = self._calculate_realized_profit(exec_price, level)
                        self._metrics.realized_profit += profit

                        self._metrics.protected_profit += profit

                except Exception as e:
                    logger.error(f"Failed to execute stop order {order_id}: {e}")
                    # Place market order
                    await self._place_market_stop_order(level_index, level)

        # Check if all levels executed
        if len(self._executed_levels) == len(self._levels):
            self._state = 'EXECUTED'
            logger.info(f"Smart stop {self.id} fully executed")

    async def _place_market_stop_order(self, level_index: int, level: SmartStopLevel):
        """Place market stop order as fallback"""
        if not self._broker:
            return

        try:
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
                self._executed_levels.append(level_index)
                self._remaining_size -= order_size

                profit = self._calculate_realized_profit(result.get('price', level.price), level)
                self._metrics.realized_profit += profit
                self._metrics.protected_profit += profit

        except Exception as e:
            logger.error(f"Failed to place market stop order: {e}")

    def _calculate_realized_profit(self, exec_price: float, level: SmartStopLevel) -> float:
        """Calculate realized profit for a stop execution"""
        if self._entry_price is None:
            return 0

        size = self._position_size * (level.size_percent / 100)

        if self._trade_direction == OrderSide.BUY:
            return (exec_price - self._entry_price) * size
        else:
            return (self._entry_price - exec_price) * size

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
            await self.check_trigger()

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
        """Convert smart stop to dictionary"""
        return {
            'id': self.id,
            'state': self._state,
            'config': self.config.model_dump(),
            'metrics': self._metrics.model_dump(),
            'entry_price': self._entry_price,
            'current_price': self._current_price,
            'current_stop': self._current_stop,
            'direction': self._trade_direction.value if self._trade_direction else None,
            'position_size': self._position_size,
            'remaining_size': self._remaining_size,
            'levels': [level.model_dump() for level in self._levels],
            'executed_levels': self._executed_levels,
            'order_ids': self._order_ids,
            'breakeven_triggered': self._breakeven_triggered,
            'trailing_started': self._trailing_started
        }

    @classmethod
    async def from_dict(
        cls,
        data: Dict[str, Any],
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ) -> 'SmartStop':
        """Create smart stop from dictionary"""
        config = SmartStopConfig(**data.get('config', {}))
        smart_stop = cls(config=config, broker=broker, order_manager=order_manager)

        # Restore state
        smart_stop._state = data.get('state', 'INACTIVE')
        smart_stop._entry_price = data.get('entry_price')
        smart_stop._current_price = data.get('current_price')
        smart_stop._current_stop = data.get('current_stop')
        smart_stop._position_size = data.get('position_size')
        smart_stop._remaining_size = data.get('remaining_size')
        smart_stop._executed_levels = data.get('executed_levels', [])
        smart_stop._breakeven_triggered = data.get('breakeven_triggered', False)
        smart_stop._trailing_started = data.get('trailing_started', False)

        if data.get('direction'):
            smart_stop._trade_direction = OrderSide(data.get('direction'))

        # Restore levels
        if data.get('levels'):
            smart_stop._levels = [SmartStopLevel(**level) for level in data.get('levels')]

        # Restore order IDs
        if data.get('order_ids'):
            smart_stop._order_ids = {int(k): v for k, v in data.get('order_ids').items()}

        # Restore metrics
        if data.get('metrics'):
            smart_stop._metrics = SmartStopMetrics(**data.get('metrics'))

        return smart_stop

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cancel()
        await self.stop_price_monitoring()
