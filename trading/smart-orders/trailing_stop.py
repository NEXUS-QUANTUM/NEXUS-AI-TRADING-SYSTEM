"""
NEXUS AI TRADING SYSTEM - Trailing Stop Smart Order Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/trailing_stop.py
Version: 1.0.0
Description: Advanced trailing stop implementation with full API integration
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
    round_to_tick_size
)
from shared.constants.trading_constants import (
    MIN_TRAILING_DISTANCE,
    DEFAULT_TRAILING_ACTIVATION,
    MAX_TRAILING_STEPS
)
from shared.interfaces.broker import BrokerInterface
from trading.smart_orders.base_order import SmartOrder, SmartOrderConfig
from trading.smart_orders.order_manager import OrderManager

logger = logging.getLogger(__name__)


class TrailingStopType(str, Enum):
    """Types of trailing stop mechanisms"""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    ATR = "atr"
    VOLATILITY = "volatility"
    DYNAMIC = "dynamic"


class TrailingStopMode(str, Enum):
    """Trailing stop modes"""
    STANDARD = "standard"  # Traditional trailing stop
    STEPPED = "stepped"  # Step-based trailing stop
    ACCELERATED = "accelerated"  # Accelerates as price moves
    DECELERATED = "decelerated"  # Decelerates as price moves
    ADAPTIVE = "adaptive"  # Adapts to market conditions


class TrailingStopState(str, Enum):
    """States of a trailing stop order"""
    INACTIVE = "inactive"
    ACTIVE = "active"  # Tracking price but not triggered
    TRIGGERED = "triggered"  # Stop price reached, order executing
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TrailingStopMetrics(BaseModel):
    """Metrics for trailing stop performance analysis"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    highest_price: Optional[float] = Field(None, description="Highest price reached since activation")
    lowest_price: Optional[float] = Field(None, description="Lowest price reached since activation")
    current_stop_price: Optional[float] = Field(None, description="Current trailing stop price")
    initial_stop_price: Optional[float] = Field(None, description="Initial stop price")
    activation_price: Optional[float] = Field(None, description="Price at activation")
    total_moves: int = Field(0, description="Number of times stop has been moved")
    max_favorable_excursion: float = Field(0.0, description="Maximum favorable price movement")
    max_adverse_excursion: float = Field(0.0, description="Maximum adverse price movement")
    current_breathing: float = Field(0.0, description="Current price breathing")
    distance_from_stop: Optional[float] = Field(None, description="Current distance from stop")
    time_activated: Optional[datetime] = Field(None, description="Time when stop was activated")
    time_triggered: Optional[datetime] = Field(None, description="Time when stop was triggered")


class TrailingStopConfig(SmartOrderConfig):
    """Configuration for trailing stop order"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    stop_type: TrailingStopType = Field(default=TrailingStopType.PERCENTAGE)
    trailing_distance: Optional[float] = Field(None, description="Distance to trail (percentage or fixed)")
    activation_distance: Optional[float] = Field(None, description="Distance required to activate trailing")
    mode: TrailingStopMode = Field(default=TrailingStopMode.STANDARD)

    # Percentage-based settings
    trailing_percent: Optional[float] = Field(None, description="Trailing percentage (1.0 = 1%)")
    activation_percent: Optional[float] = Field(None, description="Activation percentage")

    # Fixed settings
    trailing_amount: Optional[float] = Field(None, description="Fixed trailing amount")
    activation_amount: Optional[float] = Field(None, description="Fixed activation amount")

    # ATR settings
    atr_multiplier: float = Field(2.0, description="ATR multiplier for trailing distance")
    atr_period: int = Field(14, description="ATR calculation period")
    atr_activation_multiplier: float = Field(1.5, description="ATR multiplier for activation")

    # Dynamic settings
    min_trailing_distance: Optional[float] = Field(None, description="Minimum trailing distance")
    max_trailing_distance: Optional[float] = Field(None, description="Maximum trailing distance")
    step_size: Optional[float] = Field(None, description="Step size for stepped trailing")
    acceleration_factor: float = Field(0.1, description="Acceleration factor")
    deceleration_factor: float = Field(0.1, description="Deceleration factor")

    # Adaptive settings
    volatility_window: int = Field(20, description="Volatility calculation window")
    adaptation_speed: float = Field(0.5, description="Adaptation speed (0-1)")

    # Order settings
    order_size: float = Field(..., description="Size of the order")
    limit_offset: Optional[float] = Field(None, description="Offset for limit orders")
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    expire_after: Optional[timedelta] = Field(None, description="Expiration time")
    max_slippage: float = Field(0.01, description="Maximum allowed slippage")

    # Risk settings
    max_drawdown: Optional[float] = Field(None, description="Maximum drawdown allowed")
    min_profit_to_trail: Optional[float] = Field(None, description="Minimum profit required to start trailing")
    trail_only_in_profit: bool = Field(True, description="Only trail when in profit")

    # Execution settings
    use_market_orders: bool = Field(False, description="Use market orders instead of limit")
    cancel_on_exit: bool = Field(True, description="Cancel if position exits")
    allow_partial_fill: bool = Field(False, description="Allow partial fills")
    priority: int = Field(5, description="Order priority (1-10)")

    @validator('trailing_percent')
    def validate_percentage(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Trailing percentage must be positive")
        return v

    @validator('trailing_amount')
    def validate_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Trailing amount must be positive")
        return v

    @validator('atr_multiplier')
    def validate_atr(cls, v):
        if v <= 0:
            raise ValueError("ATR multiplier must be positive")
        return v

    @validator('acceleration_factor')
    def validate_acceleration(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Acceleration factor must be between 0 and 1")
        return v

    @validator('decaderation_factor')
    def validate_decaderation(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Deceleration factor must be between 0 and 1")
        return v

    @validator('adaptation_speed')
    def validate_adaptation(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Adaptation speed must be between 0 and 1")
        return v


class TrailingStopExecution(BaseModel):
    """Execution result for trailing stop"""
    order_id: str
    stop_order_id: Optional[str] = None
    executed_price: float
    executed_size: float
    status: OrderStatus
    timestamp: datetime
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class TrailingStop(SmartOrder):
    """
    Advanced trailing stop implementation with full API integration.
    
    Supports multiple trailing mechanisms:
    - Percentage-based trailing
    - Fixed amount trailing
    - ATR-based trailing
    - Volatility-based trailing
    - Dynamic trailing with acceleration/deceleration
    
    Features:
    - Multiple trailing modes (standard, stepped, accelerated, etc.)
    - Performance metrics tracking
    - Adaptive trailing based on market conditions
    - Full broker API integration
    - Real-time price monitoring
    - WebSocket support for price updates
    """

    def __init__(
        self,
        config: TrailingStopConfig,
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ):
        """
        Initialize trailing stop order.

        Args:
            config: Trailing stop configuration
            broker: Optional broker interface for execution
            order_manager: Optional order manager for coordination
        """
        super().__init__(config=config, broker=broker, order_manager=order_manager)
        self.config = config
        self._metrics = TrailingStopMetrics()
        self._state = TrailingStopState.INACTIVE
        self._stop_price: Optional[float] = None
        self._current_price: Optional[float] = None
        self._entry_price: Optional[float] = None
        self._trade_direction: Optional[OrderSide] = None
        self._position_size: Optional[float] = None
        self._stop_order_id: Optional[str] = None
        self._order_queue: List[Dict[str, Any]] = []
        self._subscription_id: Optional[str] = None

        # Price history for calculations
        self._price_history: List[float] = []
        self._timestamp_history: List[datetime] = []
        self._max_history_length = 1000

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(f"Initialized TrailingStop with ID: {self.id}")

    async def activate(self, price: float, direction: OrderSide, size: float) -> bool:
        """
        Activate the trailing stop.

        Args:
            price: Entry price
            direction: Trade direction (BUY/SELL)
            size: Position size

        Returns:
            bool: True if activated successfully
        """
        async with self._lock:
            if self._state != TrailingStopState.INACTIVE:
                logger.warning(f"Trailing stop {self.id} already active")
                return False

            self._entry_price = price
            self._trade_direction = direction
            self._position_size = size

            # Calculate initial stop
            self._stop_price = self._calculate_initial_stop(price)
            if self._stop_price is None:
                logger.error(f"Failed to calculate initial stop for {self.id}")
                return False

            # Set metrics
            self._metrics.activation_price = price
            self._metrics.initial_stop_price = self._stop_price
            self._metrics.current_stop_price = self._stop_price
            self._metrics.highest_price = price
            self._metrics.lowest_price = price
            self._metrics.time_activated = datetime.utcnow()

            self._state = TrailingStopState.ACTIVE
            self._current_price = price

            # Submit stop order to broker
            if self._broker:
                await self._submit_stop_order()

            logger.info(
                f"Trailing stop {self.id} activated at price {price}, "
                f"stop: {self._stop_price}, direction: {direction.value}"
            )

            return True

    async def update_price(self, new_price: float, timestamp: Optional[datetime] = None) -> Optional[float]:
        """
        Update current price and recalculate trailing stop.

        Args:
            new_price: Current market price
            timestamp: Optional timestamp of price update

        Returns:
            Optional[float]: New stop price if updated, None otherwise
        """
        async with self._lock:
            if self._state not in [TrailingStopState.ACTIVE, TrailingStopState.TRIGGERED]:
                return None

            self._current_price = new_price

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

            # Check if we should update the stop
            updated_stop = self._calculate_trailing_stop(new_price)

            if updated_stop != self._stop_price:
                self._stop_price = updated_stop
                self._metrics.current_stop_price = updated_stop
                self._metrics.total_moves += 1

                # Update stop order on broker
                if self._broker and self._stop_order_id:
                    await self._update_stop_order(new_stop_price=updated_stop)

                logger.debug(
                    f"Trailing stop {self.id} updated: stop_price={updated_stop}, "
                    f"current_price={new_price}, moves={self._metrics.total_moves}"
                )

                return updated_stop

            return None

    async def check_trigger(self, price: Optional[float] = None) -> bool:
        """
        Check if the trailing stop should be triggered.

        Args:
            price: Current price to check against

        Returns:
            bool: True if triggered
        """
        async with self._lock:
            if self._state != TrailingStopState.ACTIVE:
                return False

            check_price = price or self._current_price
            if check_price is None:
                return False

            triggered = False

            if self._trade_direction == OrderSide.BUY:
                # For long positions, stop triggered when price falls below stop
                if check_price <= self._stop_price:
                    triggered = True
            else:  # SELL
                # For short positions, stop triggered when price rises above stop
                if check_price >= self._stop_price:
                    triggered = True

            if triggered:
                self._state = TrailingStopState.TRIGGERED
                self._metrics.time_triggered = datetime.utcnow()

                await self._execute_stop_order()
                logger.info(f"Trailing stop {self.id} triggered at price {check_price}")

            return triggered

    async def cancel(self) -> bool:
        """
        Cancel the trailing stop.

        Returns:
            bool: True if cancelled successfully
        """
        async with self._lock:
            if self._state in [TrailingStopState.CANCELLED, TrailingStopState.EXECUTED]:
                return False

            self._state = TrailingStopState.CANCELLED

            if self._broker and self._stop_order_id:
                try:
                    await self._broker.cancel_order(self._stop_order_id)
                except Exception as e:
                    logger.error(f"Failed to cancel stop order {self._stop_order_id}: {e}")

            logger.info(f"Trailing stop {self.id} cancelled")

            return True

    async def get_metrics(self) -> TrailingStopMetrics:
        """Get current trailing stop metrics"""
        async with self._lock:
            metrics = self._metrics.model_copy()
            metrics.distance_from_stop = self._calculate_distance_from_stop()
            return metrics

    def get_state(self) -> TrailingStopState:
        """Get current state of trailing stop"""
        return self._state

    def get_stop_price(self) -> Optional[float]:
        """Get current stop price"""
        return self._stop_price

    def get_current_price(self) -> Optional[float]:
        """Get current price"""
        return self._current_price

    def get_trail_distance(self) -> Optional[float]:
        """Get current trailing distance"""
        if self._stop_price is None or self._current_price is None:
            return None
        return abs(self._current_price - self._stop_price)

    def get_trail_percentage(self) -> Optional[float]:
        """Get current trailing percentage"""
        if self._stop_price is None or self._current_price is None or self._current_price == 0:
            return None
        return abs((self._current_price - self._stop_price) / self._current_price) * 100

    def _calculate_initial_stop(self, price: float) -> Optional[float]:
        """Calculate initial stop price"""
        if self.config.stop_type == TrailingStopType.PERCENTAGE:
            if self.config.activation_percent is not None:
                if self._trade_direction == OrderSide.BUY:
                    return price * (1 - self.config.activation_percent / 100)
                else:
                    return price * (1 + self.config.activation_percent / 100)
            elif self.config.activation_amount is not None:
                if self._trade_direction == OrderSide.BUY:
                    return price - self.config.activation_amount
                else:
                    return price + self.config.activation_amount
            elif self.config.activation_distance is not None:
                if self._trade_direction == OrderSide.BUY:
                    return price - self.config.activation_distance
                else:
                    return price + self.config.activation_distance
            else:
                # Use default activation
                if self._trade_direction == OrderSide.BUY:
                    return price * (1 - DEFAULT_TRAILING_ACTIVATION)
                else:
                    return price * (1 + DEFAULT_TRAILING_ACTIVATION)

        elif self.config.stop_type == TrailingStopType.FIXED:
            if self._trade_direction == OrderSide.BUY:
                return price - (self.config.trailing_amount or 0.01)
            else:
                return price + (self.config.trailing_amount or 0.01)

        elif self.config.stop_type == TrailingStopType.ATR:
            # Use ATR calculation
            atr = self._calculate_atr()
            if atr is None:
                atr = price * 0.01  # Fallback to 1%
            if self._trade_direction == OrderSide.BUY:
                return price - (atr * self.config.atr_activation_multiplier)
            else:
                return price + (atr * self.config.atr_activation_multiplier)

        elif self.config.stop_type == TrailingStopType.VOLATILITY:
            volatility = self._calculate_volatility()
            if volatility is None:
                volatility = 0.01  # Fallback to 1%
            if self._trade_direction == OrderSide.BUY:
                return price * (1 - volatility * 2)
            else:
                return price * (1 + volatility * 2)

        elif self.config.stop_type == TrailingStopType.DYNAMIC:
            return self._calculate_dynamic_initial_stop(price)

        return None

    def _calculate_trailing_stop(self, current_price: float) -> float:
        """Calculate trailing stop price based on current configuration"""
        if self._trade_direction == OrderSide.BUY:
            # For long positions
            base_stop = self._calculate_base_stop_buy(current_price)
            if self.config.mode == TrailingStopMode.STANDARD:
                return base_stop

            elif self.config.mode == TrailingStopMode.STEPPED:
                return self._apply_stepped_trailing_buy(current_price, base_stop)

            elif self.config.mode == TrailingStopMode.ACCELERATED:
                return self._apply_accelerated_trailing_buy(current_price, base_stop)

            elif self.config.mode == TrailingStopMode.DECELERATED:
                return self._apply_decelerated_trailing_buy(current_price, base_stop)

            elif self.config.mode == TrailingStopMode.ADAPTIVE:
                return self._apply_adaptive_trailing_buy(current_price, base_stop)

        else:
            # For short positions
            base_stop = self._calculate_base_stop_sell(current_price)
            if self.config.mode == TrailingStopMode.STANDARD:
                return base_stop

            elif self.config.mode == TrailingStopMode.STEPPED:
                return self._apply_stepped_trailing_sell(current_price, base_stop)

            elif self.config.mode == TrailingStopMode.ACCELERATED:
                return self._apply_accelerated_trailing_sell(current_price, base_stop)

            elif self.config.mode == TrailingStopMode.DECELERATED:
                return self._apply_decelerated_trailing_sell(current_price, base_stop)

            elif self.config.mode == TrailingStopMode.ADAPTIVE:
                return self._apply_adaptive_trailing_sell(current_price, base_stop)

        return self._stop_price or current_price

    def _calculate_base_stop_buy(self, current_price: float) -> float:
        """Calculate base trailing stop for buy positions"""
        if self.config.stop_type == TrailingStopType.PERCENTAGE:
            if self.config.trailing_percent:
                return current_price * (1 - self.config.trailing_percent / 100)
            return current_price * (1 - 0.01)  # Default 1%

        elif self.config.stop_type == TrailingStopType.FIXED:
            return current_price - (self.config.trailing_amount or 0.01)

        elif self.config.stop_type == TrailingStopType.ATR:
            atr = self._calculate_atr()
            if atr is None:
                atr = current_price * 0.01
            return current_price - (atr * self.config.atr_multiplier)

        elif self.config.stop_type == TrailingStopType.VOLATILITY:
            volatility = self._calculate_volatility()
            if volatility is None:
                volatility = 0.01
            return current_price * (1 - volatility * 2)

        elif self.config.stop_type == TrailingStopType.DYNAMIC:
            return self._calculate_dynamic_stop_buy(current_price)

        return current_price * 0.99

    def _calculate_base_stop_sell(self, current_price: float) -> float:
        """Calculate base trailing stop for sell positions"""
        if self.config.stop_type == TrailingStopType.PERCENTAGE:
            if self.config.trailing_percent:
                return current_price * (1 + self.config.trailing_percent / 100)
            return current_price * (1 + 0.01)  # Default 1%

        elif self.config.stop_type == TrailingStopType.FIXED:
            return current_price + (self.config.trailing_amount or 0.01)

        elif self.config.stop_type == TrailingStopType.ATR:
            atr = self._calculate_atr()
            if atr is None:
                atr = current_price * 0.01
            return current_price + (atr * self.config.atr_multiplier)

        elif self.config.stop_type == TrailingStopType.VOLATILITY:
            volatility = self._calculate_volatility()
            if volatility is None:
                volatility = 0.01
            return current_price * (1 + volatility * 2)

        elif self.config.stop_type == TrailingStopType.DYNAMIC:
            return self._calculate_dynamic_stop_sell(current_price)

        return current_price * 1.01

    def _apply_stepped_trailing_buy(self, current_price: float, base_stop: float) -> float:
        """Apply stepped trailing for buy positions"""
        if self.config.step_size is None:
            return base_stop

        # Only move stop in steps
        step_price = self._stop_price or current_price
        difference = base_stop - step_price

        # Check if difference exceeds step size
        if difference >= self.config.step_size:
            # Move stop up by step size
            return step_price + self.config.step_size

        return step_price

    def _apply_stepped_trailing_sell(self, current_price: float, base_stop: float) -> float:
        """Apply stepped trailing for sell positions"""
        if self.config.step_size is None:
            return base_stop

        step_price = self._stop_price or current_price
        difference = step_price - base_stop

        if difference >= self.config.step_size:
            return step_price - self.config.step_size

        return step_price

    def _apply_accelerated_trailing_buy(self, current_price: float, base_stop: float) -> float:
        """Apply accelerated trailing for buy positions"""
        if self._entry_price is None:
            return base_stop

        # Calculate profit percentage
        profit_percent = (current_price - self._entry_price) / self._entry_price * 100

        # Apply acceleration
        acceleration = 1 + (profit_percent / 100) * self.config.acceleration_factor

        # Adjust trailing distance
        base_distance = (current_price - base_stop)
        adjusted_distance = base_distance * (1 + (profit_percent / 100) * self.config.acceleration_factor)

        return current_price - adjusted_distance

    def _apply_accelerated_trailing_sell(self, current_price: float, base_stop: float) -> float:
        """Apply accelerated trailing for sell positions"""
        if self._entry_price is None:
            return base_stop

        profit_percent = (self._entry_price - current_price) / self._entry_price * 100

        base_distance = (base_stop - current_price)
        adjusted_distance = base_distance * (1 + (profit_percent / 100) * self.config.acceleration_factor)

        return current_price + adjusted_distance

    def _apply_decelerated_trailing_buy(self, current_price: float, base_stop: float) -> float:
        """Apply decelerated trailing for buy positions"""
        if self._entry_price is None:
            return base_stop

        profit_percent = (current_price - self._entry_price) / self._entry_price * 100

        base_distance = (current_price - base_stop)
        adjusted_distance = base_distance * (1 - (profit_percent / 100) * self.config.deceleration_factor)

        return current_price - max(adjusted_distance, MIN_TRAILING_DISTANCE)

    def _apply_decelerated_trailing_sell(self, current_price: float, base_stop: float) -> float:
        """Apply decelerated trailing for sell positions"""
        if self._entry_price is None:
            return base_stop

        profit_percent = (self._entry_price - current_price) / self._entry_price * 100

        base_distance = (base_stop - current_price)
        adjusted_distance = base_distance * (1 - (profit_percent / 100) * self.config.deceleration_factor)

        return current_price + max(adjusted_distance, MIN_TRAILING_DISTANCE)

    def _apply_adaptive_trailing_buy(self, current_price: float, base_stop: float) -> float:
        """Apply adaptive trailing for buy positions"""
        # Calculate current volatility
        volatility = self._calculate_volatility()
        if volatility is None:
            return base_stop

        # Calculate price momentum
        momentum = self._calculate_momentum()

        # Adjust trailing distance based on volatility and momentum
        base_distance = current_price - base_stop

        # Increase distance in high volatility, decrease in low volatility
        volatility_factor = 1 + (volatility - 0.01) * 10 * self.config.adaptation_speed

        # Adjust based on momentum
        momentum_factor = 1 + (momentum * 0.1 * self.config.adaptation_speed)

        adjusted_distance = base_distance * volatility_factor * momentum_factor

        # Apply limits
        if self.config.min_trailing_distance:
            adjusted_distance = max(adjusted_distance, self.config.min_trailing_distance)
        if self.config.max_trailing_distance:
            adjusted_distance = min(adjusted_distance, self.config.max_trailing_distance)

        return current_price - adjusted_distance

    def _apply_adaptive_trailing_sell(self, current_price: float, base_stop: float) -> float:
        """Apply adaptive trailing for sell positions"""
        volatility = self._calculate_volatility()
        if volatility is None:
            return base_stop

        momentum = self._calculate_momentum()

        base_distance = base_stop - current_price

        volatility_factor = 1 + (volatility - 0.01) * 10 * self.config.adaptation_speed
        momentum_factor = 1 - (momentum * 0.1 * self.config.adaptation_speed)

        adjusted_distance = base_distance * volatility_factor * momentum_factor

        if self.config.min_trailing_distance:
            adjusted_distance = max(adjusted_distance, self.config.min_trailing_distance)
        if self.config.max_trailing_distance:
            adjusted_distance = min(adjusted_distance, self.config.max_trailing_distance)

        return current_price + adjusted_distance

    def _calculate_dynamic_initial_stop(self, price: float) -> float:
        """Calculate initial stop using dynamic method"""
        volatility = self._calculate_volatility()
        if volatility is None:
            volatility = 0.02

        # Use recent price data to determine optimal stop
        if len(self._price_history) >= 10:
            # Calculate average true range
            ranges = []
            for i in range(1, min(10, len(self._price_history))):
                ranges.append(abs(self._price_history[i] - self._price_history[i-1]))
            avg_range = sum(ranges) / len(ranges)

            # Use dynamic factor
            dynamic_factor = max(2, min(5, 1 / volatility))
            if self._trade_direction == OrderSide.BUY:
                return price - (avg_range * dynamic_factor)
            else:
                return price + (avg_range * dynamic_factor)

        if self._trade_direction == OrderSide.BUY:
            return price * (1 - 0.02)
        else:
            return price * (1 + 0.02)

    def _calculate_dynamic_stop_buy(self, current_price: float) -> float:
        """Calculate dynamic stop for buy positions"""
        if len(self._price_history) >= 14:
            # Use ATR with dynamic multiplier
            atr = self._calculate_atr()
            if atr:
                multiplier = self._calculate_dynamic_multiplier()
                return current_price - (atr * multiplier)

        # Fallback to percentage
        return current_price * 0.99

    def _calculate_dynamic_stop_sell(self, current_price: float) -> float:
        """Calculate dynamic stop for sell positions"""
        if len(self._price_history) >= 14:
            atr = self._calculate_atr()
            if atr:
                multiplier = self._calculate_dynamic_multiplier()
                return current_price + (atr * multiplier)

        return current_price * 1.01

    def _calculate_dynamic_multiplier(self) -> float:
        """Calculate dynamic multiplier based on market conditions"""
        volatility = self._calculate_volatility()
        if volatility is None:
            return 2.0

        # Use higher multiplier in low volatility, lower in high volatility
        base_multiplier = 2.0
        volatility_adjustment = (0.02 - volatility) * 50
        return max(1.0, min(5.0, base_multiplier + volatility_adjustment))

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

        # Calculate standard deviation of returns
        returns = []
        for i in range(1, self.config.volatility_window):
            if self._price_history[i-1] != 0:
                returns.append((self._price_history[i] - self._price_history[i-1]) / self._price_history[i-1])

        if not returns:
            return None

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return variance ** 0.5

    def _calculate_momentum(self) -> float:
        """Calculate price momentum"""
        if len(self._price_history) < 10:
            return 0

        # Simple momentum calculation
        recent_avg = sum(self._price_history[-5:]) / 5
        older_avg = sum(self._price_history[-10:-5]) / 5

        if older_avg == 0:
            return 0

        return (recent_avg - older_avg) / older_avg

    def _calculate_distance_from_stop(self) -> Optional[float]:
        """Calculate current distance from stop"""
        if self._current_price is None or self._stop_price is None:
            return None
        return abs(self._current_price - self._stop_price)

    async def _submit_stop_order(self):
        """Submit stop order to broker"""
        if not self._broker or self._stop_price is None:
            return

        try:
            # Determine order side (opposite of position)
            order_side = OrderSide.SELL if self._trade_direction == OrderSide.BUY else OrderSide.BUY

            # Create stop order
            order_params = {
                'symbol': self.config.symbol,
                'side': order_side,
                'order_type': OrderType.STOP_MARKET if self.config.use_market_orders else OrderType.STOP_LIMIT,
                'stop_price': self._stop_price,
                'quantity': self._position_size or self.config.order_size,
                'time_in_force': self.config.time_in_force,
                'client_order_id': self.id
            }

            if not self.config.use_market_orders and self.config.limit_offset is not None:
                if order_side == OrderSide.SELL:
                    order_params['limit_price'] = self._stop_price - self.config.limit_offset
                else:
                    order_params['limit_price'] = self._stop_price + self.config.limit_offset

            # Submit order
            result = await self._broker.place_order(**order_params)
            self._stop_order_id = result.get('order_id')

            logger.info(f"Submitted stop order {self._stop_order_id} at {self._stop_price}")

        except Exception as e:
            logger.error(f"Failed to submit stop order: {e}")
            raise

    async def _update_stop_order(self, new_stop_price: float):
        """Update stop order on broker"""
        if not self._broker or not self._stop_order_id:
            return

        try:
            await self._broker.update_order(
                order_id=self._stop_order_id,
                stop_price=new_stop_price
            )
            logger.debug(f"Updated stop order {self._stop_order_id} to {new_stop_price}")

        except Exception as e:
            logger.error(f"Failed to update stop order: {e}")
            # Try to re-submit
            await self._resubmit_stop_order(new_stop_price)

    async def _resubmit_stop_order(self, stop_price: float):
        """Resubmit stop order if update fails"""
        if not self._broker:
            return

        try:
            # Cancel existing
            await self._broker.cancel_order(self._stop_order_id)

            # Submit new
            order_side = OrderSide.SELL if self._trade_direction == OrderSide.BUY else OrderSide.BUY
            order_params = {
                'symbol': self.config.symbol,
                'side': order_side,
                'order_type': OrderType.STOP_MARKET if self.config.use_market_orders else OrderType.STOP_LIMIT,
                'stop_price': stop_price,
                'quantity': self._position_size or self.config.order_size,
                'time_in_force': self.config.time_in_force,
                'client_order_id': f"{self.id}_{int(datetime.utcnow().timestamp())}"
            }

            result = await self._broker.place_order(**order_params)
            self._stop_order_id = result.get('order_id')

            logger.info(f"Resubmitted stop order {self._stop_order_id} at {stop_price}")

        except Exception as e:
            logger.error(f"Failed to resubmit stop order: {e}")

    async def _execute_stop_order(self):
        """Execute the stop order when triggered"""
        if not self._broker or self._stop_order_id is None:
            return

        try:
            # Check order status
            order_status = await self._broker.get_order_status(self._stop_order_id)

            if order_status.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                self._state = TrailingStopState.EXECUTED
                logger.info(f"Stop order {self._stop_order_id} executed")

            elif order_status.get('status') in ['PENDING', 'WORKING']:
                # Order already working, nothing to do
                pass

            elif order_status.get('status') in ['CANCELLED', 'REJECTED', 'EXPIRED']:
                # Order failed, try to place new order
                await self._place_immediate_stop_order()

        except Exception as e:
            logger.error(f"Failed to execute stop order: {e}")
            await self._place_immediate_stop_order()

    async def _place_immediate_stop_order(self):
        """Place an immediate stop order when triggered"""
        if not self._broker or self._current_price is None:
            return

        try:
            order_side = OrderSide.SELL if self._trade_direction == OrderSide.BUY else OrderSide.BUY

            order_params = {
                'symbol': self.config.symbol,
                'side': order_side,
                'order_type': OrderType.MARKET,
                'quantity': self._position_size or self.config.order_size,
                'time_in_force': TimeInForce.IOC
            }

            result = await self._broker.place_order(**order_params)

            if result.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                self._state = TrailingStopState.EXECUTED
                logger.info(f"Immediate stop order executed: {result}")

            self._stop_order_id = result.get('order_id')

        except Exception as e:
            logger.error(f"Failed to place immediate stop order: {e}")
            self._state = TrailingStopState.ERROR

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
                # Unsubscribe from WebSocket
                if hasattr(self._broker, 'unsubscribe'):
                    await self._broker.unsubscribe(self._subscription_id)
                self._subscription_id = None
                logger.info("Stopped price monitoring")

            except Exception as e:
                logger.error(f"Failed to stop price monitoring: {e}")

    async def to_dict(self) -> Dict[str, Any]:
        """Convert trailing stop to dictionary"""
        return {
            'id': self.id,
            'state': self._state.value,
            'config': self.config.model_dump(),
            'metrics': self._metrics.model_dump(),
            'stop_price': self._stop_price,
            'current_price': self._current_price,
            'entry_price': self._entry_price,
            'direction': self._trade_direction.value if self._trade_direction else None,
            'position_size': self._position_size,
            'stop_order_id': self._stop_order_id
        }

    @classmethod
    async def from_dict(
        cls,
        data: Dict[str, Any],
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ) -> 'TrailingStop':
        """Create trailing stop from dictionary"""
        config = TrailingStopConfig(**data.get('config', {}))
        trailing_stop = cls(config=config, broker=broker, order_manager=order_manager)

        # Restore state
        trailing_stop._state = TrailingStopState(data.get('state', 'inactive'))
        trailing_stop._stop_price = data.get('stop_price')
        trailing_stop._current_price = data.get('current_price')
        trailing_stop._entry_price = data.get('entry_price')
        trailing_stop._position_size = data.get('position_size')
        trailing_stop._stop_order_id = data.get('stop_order_id')

        if data.get('direction'):
            trailing_stop._trade_direction = OrderSide(data.get('direction'))

        # Restore metrics
        if data.get('metrics'):
            trailing_stop._metrics = TrailingStopMetrics(**data.get('metrics'))

        return trailing_stop

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cancel()
        await self.stop_price_monitoring()
