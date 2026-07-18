"""
NEXUS AI TRADING SYSTEM - Scaling Order Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/scaling_order.py
Version: 1.0.0
Description: Advanced scaling order implementation with full API integration
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
    calculate_vwap,
    calculate_volume_profile
)
from shared.constants.trading_constants import (
    MIN_ORDER_SIZE,
    MAX_SCALING_ORDERS,
    DEFAULT_SCALING_STEPS
)
from shared.interfaces.broker import BrokerInterface
from trading.smart_orders.base_order import SmartOrder, SmartOrderConfig
from trading.smart_orders.order_manager import OrderManager

logger = logging.getLogger(__name__)


class ScalingType(str, Enum):
    """Types of scaling mechanisms"""
    FIXED = "fixed"                  # Fixed price intervals
    PERCENTAGE = "percentage"        # Percentage-based intervals
    ATR = "atr"                      # ATR-based intervals
    VOLATILITY = "volatility"        # Volatility-based intervals
    SUPPORT_RESISTANCE = "sr"        # Support/Resistance levels
    VOLUME_PROFILE = "volume"        # Volume profile based
    VWAP = "vwap"                    # VWAP-based intervals
    TIME = "time"                    # Time-based scaling
    PYRAMID = "pyramid"              # Pyramid scaling
    MARTINGALE = "martingale"        # Martingale scaling
    FIBONACCI = "fibonacci"          # Fibonacci-based scaling


class ScalingDirection(str, Enum):
    """Scaling direction"""
    BUY = "buy"                      # Scale into buy positions
    SELL = "sell"                    # Scale into sell positions
    BOTH = "both"                    # Both directions
    AVERAGE = "average"              # Average into position
    ADD = "add"                      # Add to position
    REDUCE = "reduce"                # Reduce position


class ScalingMode(str, Enum):
    """Scaling modes"""
    LINEAR = "linear"                # Linear price distribution
    LOGARITHMIC = "logarithmic"      # Logarithmic distribution
    EXPONENTIAL = "exponential"      # Exponential distribution
    ADAPTIVE = "adaptive"            # Adaptive distribution
    DCA = "dca"                      # Dollar Cost Averaging
    PYRAMID = "pyramid"              # Pyramid scaling
    REVERSE = "reverse"              # Reverse scaling


class ScalingLevel(BaseModel):
    """Individual scaling level configuration"""
    price: float = Field(..., description="Price level")
    size: float = Field(..., description="Size to trade at this level")
    size_percent: Optional[float] = Field(None, description="Percentage of total size")
    priority: int = Field(1, description="Priority order")
    type: ScalingType = Field(default=ScalingType.FIXED)
    limit_price: Optional[float] = Field(None, description="Limit price")
    stop_price: Optional[float] = Field(None, description="Stop price")
    order_type: OrderType = Field(default=OrderType.LIMIT)
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    expire_at: Optional[datetime] = Field(None, description="Expiration time")
    description: Optional[str] = Field(None, description="Description of this level")


class ScalingMetrics(BaseModel):
    """Metrics for scaling order performance"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    entry_price: Optional[float] = Field(None, description="Initial entry price")
    current_price: Optional[float] = Field(None, description="Current market price")
    average_price: Optional[float] = Field(None, description="Average execution price")
    total_size: float = Field(0.0, description="Total size accumulated")
    filled_size: float = Field(0.0, description="Total filled size")
    remaining_size: float = Field(0.0, description="Remaining size to fill")
    
    levels_executed: int = Field(0, description="Number of levels executed")
    total_levels: int = Field(0, description="Total number of levels")
    
    realized_pnl: float = Field(0.0, description="Realized P&L")
    unrealized_pnl: float = Field(0.0, description="Unrealized P&L")
    total_pnl: float = Field(0.0, description="Total P&L")
    
    max_drawdown: float = Field(0.0, description="Maximum drawdown")
    max_runup: float = Field(0.0, description="Maximum runup")
    
    fill_rate: float = Field(0.0, description="Fill rate percentage")
    average_spread: float = Field(0.0, description="Average spread")
    total_fees: float = Field(0.0, description="Total fees paid")


class ScalingOrderConfig(SmartOrderConfig):
    """Configuration for scaling order"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    scaling_type: ScalingType = Field(default=ScalingType.FIXED)
    scaling_direction: ScalingDirection = Field(default=ScalingDirection.BUY)
    mode: ScalingMode = Field(default=ScalingMode.LINEAR)
    
    # Size settings
    total_size: float = Field(..., description="Total size to scale")
    base_size: float = Field(..., description="Base order size")
    size_step: Optional[float] = Field(None, description="Size increment per level")
    max_size_per_level: Optional[float] = Field(None, description="Maximum size per level")
    
    # Level settings
    number_of_levels: int = Field(DEFAULT_SCALING_STEPS, description="Number of scaling levels")
    min_level_distance: float = Field(0.01, description="Minimum distance between levels")
    max_level_distance: float = Field(0.05, description="Maximum distance between levels")
    
    # Price settings
    start_price: float = Field(..., description="Starting price")
    end_price: Optional[float] = Field(None, description="Ending price")
    price_step: Optional[float] = Field(None, description="Price step between levels")
    price_step_percent: Optional[float] = Field(None, description="Percentage step between levels")
    
    # Percentage settings
    percent_range: float = Field(2.0, description="Percentage range for scaling")
    percent_step: float = Field(0.5, description="Percentage step")
    
    # ATR settings
    atr_multiplier: float = Field(1.0, description="ATR multiplier")
    atr_period: int = Field(14, description="ATR period")
    
    # Volatility settings
    volatility_multiplier: float = Field(1.0, description="Volatility multiplier")
    volatility_window: int = Field(20, description="Volatility window")
    
    # Volume profile settings
    volume_profile_window: int = Field(100, description="Volume profile window")
    volume_threshold: float = Field(0.5, description="Volume threshold")
    
    # VWAP settings
    vwap_period: int = Field(20, description="VWAP period")
    vwap_deviation: float = Field(0.01, description="VWAP deviation")
    
    # Fibonacci settings
    fibonacci_levels: List[float] = Field(
        default=[0.236, 0.382, 0.5, 0.618, 0.786],
        description="Fibonacci levels"
    )
    
    # Time settings
    time_interval: Optional[timedelta] = Field(None, description="Time between levels")
    total_duration: Optional[timedelta] = Field(None, description="Total scaling duration")
    
    # Martingale settings
    martingale_multiplier: float = Field(2.0, description="Martingale multiplier")
    max_martingale_levels: int = Field(5, description="Maximum martingale levels")
    
    # Risk settings
    max_risk_per_level: float = Field(0.02, description="Maximum risk per level")
    max_total_risk: float = Field(0.10, description="Maximum total risk")
    stop_loss_percent: Optional[float] = Field(None, description="Stop loss percentage")
    take_profit_percent: Optional[float] = Field(None, description="Take profit percentage")
    risk_reward_ratio: float = Field(2.0, description="Risk-reward ratio")
    
    # Order settings
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    expire_after: Optional[timedelta] = Field(None, description="Expiration time")
    max_slippage: float = Field(0.01, description="Maximum slippage")
    allow_partial_fill: bool = Field(True, description="Allow partial fills")
    
    # Smart features
    dynamic_adjustment: bool = Field(True, description="Enable dynamic adjustment")
    cancel_on_breakeven: bool = Field(False, description="Cancel on breakeven")
    adjust_on_volume: bool = Field(False, description="Adjust on volume")
    use_market_orders: bool = Field(False, description="Use market orders")

    @validator('number_of_levels')
    def validate_levels(cls, v):
        if v < 1 or v > MAX_SCALING_ORDERS:
            raise ValueError(f"Number of levels must be between 1 and {MAX_SCALING_ORDERS}")
        return v

    @validator('total_size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Total size must be positive")
        return v

    @validator('base_size')
    def validate_base_size(cls, v):
        if v <= 0:
            raise ValueError("Base size must be positive")
        return v

    @validator('min_level_distance')
    def validate_min_distance(cls, v):
        if v < 0:
            raise ValueError("Minimum level distance must be non-negative")
        return v

    @validator('max_level_distance')
    def validate_max_distance(cls, v, values):
        if 'min_level_distance' in values and v <= values['min_level_distance']:
            raise ValueError("Max level distance must be greater than min level distance")
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


class LevelExecution(BaseModel):
    """Execution result for a scaling level"""
    level_index: int
    level_price: float
    executed_price: float
    executed_size: float
    order_id: str
    status: OrderStatus
    timestamp: datetime
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class ScalingOrder(SmartOrder):
    """
    Advanced scaling order implementation with full API integration.
    
    Supports multiple scaling mechanisms:
    - Fixed price intervals
    - Percentage-based intervals
    - ATR-based intervals
    - Volatility-based intervals
    - Support/Resistance levels
    - Volume profile based
    - VWAP-based intervals
    - Fibonacci-based scaling
    
    Features:
    - Multiple scaling modes (linear, logarithmic, exponential, etc.)
    - DCA (Dollar Cost Averaging)
    - Pyramid scaling
    - Martingale scaling
    - Dynamic adjustment
    - Full broker API integration
    - Performance metrics tracking
    """

    def __init__(
        self,
        config: ScalingOrderConfig,
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ):
        """
        Initialize scaling order.

        Args:
            config: Scaling order configuration
            broker: Optional broker interface for execution
            order_manager: Optional order manager for coordination
        """
        super().__init__(config=config, broker=broker, order_manager=order_manager)
        self.config = config
        self._metrics = ScalingMetrics()
        self._state = 'INACTIVE'
        self._current_price: Optional[float] = None
        self._levels: List[ScalingLevel] = []
        self._order_ids: Dict[int, str] = {}
        self._executed_levels: List[int] = []
        self._filled_size: float = 0.0
        self._remaining_size: float = 0.0
        self._average_price: float = 0.0
        self._total_cost: float = 0.0
        self._subscription_id: Optional[str] = None

        # Price history
        self._price_history: List[float] = []
        self._volume_history: List[float] = []
        self._timestamp_history: List[datetime] = []
        self._max_history_length = 1000

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(f"Initialized ScalingOrder with ID: {self.id}")

    async def activate(self, start_price: Optional[float] = None) -> bool:
        """
        Activate the scaling order.

        Args:
            start_price: Optional starting price

        Returns:
            bool: True if activated successfully
        """
        async with self._lock:
            if self._state in ['ACTIVE', 'EXECUTED']:
                logger.warning(f"Scaling order {self.id} already active or executed")
                return False

            if start_price:
                self.config.start_price = start_price

            # Generate scaling levels
            self._levels = await self._generate_levels()

            if not self._levels:
                logger.error(f"No scaling levels generated for {self.id}")
                return False

            # Calculate metrics
            self._metrics.total_levels = len(self._levels)
            self._metrics.total_size = self.config.total_size
            self._metrics.remaining_size = self.config.total_size
            self._metrics.entry_price = self.config.start_price
            self._metrics.current_price = self.config.start_price

            self._remaining_size = self.config.total_size
            self._state = 'ACTIVE'
            self._current_price = self.config.start_price

            # Submit orders
            if self._broker:
                await self._submit_orders()

            logger.info(
                f"Scaling order {self.id} activated at price {self.config.start_price}, "
                f"levels: {len(self._levels)}, total size: {self.config.total_size}"
            )

            return True

    async def update_price(self, new_price: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Update current price and check level triggers.

        Args:
            new_price: Current market price
            timestamp: Optional timestamp of price update

        Returns:
            bool: True if any levels were triggered
        """
        async with self._lock:
            if self._state != 'ACTIVE':
                return False

            self._current_price = new_price
            self._metrics.current_price = new_price

            # Update price history
            self._price_history.append(new_price)
            self._timestamp_history.append(timestamp or datetime.utcnow())
            if len(self._price_history) > self._max_history_length:
                self._price_history.pop(0)
                self._timestamp_history.pop(0)

            # Check for level triggers
            triggered = await self._check_levels(new_price)

            # Update metrics
            self._update_metrics(new_price)

            return triggered

    async def check_conditions(self, price: Optional[float] = None) -> bool:
        """
        Check if scaling conditions are met.

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

            return await self._check_levels(check_price)

    async def cancel(self) -> bool:
        """
        Cancel the scaling order.

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
            logger.info(f"Scaling order {self.id} cancelled")

            return True

    async def get_metrics(self) -> ScalingMetrics:
        """Get current scaling metrics"""
        async with self._lock:
            metrics = self._metrics.model_copy()
            metrics.current_price = self._current_price
            return metrics

    def get_state(self) -> str:
        """Get current state"""
        return self._state

    def get_levels(self) -> List[ScalingLevel]:
        """Get scaling levels"""
        return self._levels

    def get_filled_size(self) -> float:
        """Get filled size"""
        return self._filled_size

    def get_remaining_size(self) -> float:
        """Get remaining size"""
        return self._remaining_size

    def get_average_price(self) -> Optional[float]:
        """Get average execution price"""
        return self._average_price if self._filled_size > 0 else None

    def get_unfilled_orders(self) -> List[Dict[str, Any]]:
        """Get unfilled orders"""
        unfilled = []
        for level_index, order_id in self._order_ids.items():
            if level_index not in self._executed_levels:
                unfilled.append({
                    'level_index': level_index,
                    'order_id': order_id,
                    'level': self._levels[level_index].model_dump() if level_index < len(self._levels) else None
                })
        return unfilled

    async def _generate_levels(self) -> List[ScalingLevel]:
        """Generate scaling levels based on configuration"""
        levels = []

        if self.config.scaling_type == ScalingType.FIXED:
            levels = await self._generate_fixed_levels()

        elif self.config.scaling_type == ScalingType.PERCENTAGE:
            levels = await self._generate_percentage_levels()

        elif self.config.scaling_type == ScalingType.ATR:
            levels = await self._generate_atr_levels()

        elif self.config.scaling_type == ScalingType.VOLATILITY:
            levels = await self._generate_volatility_levels()

        elif self.config.scaling_type == ScalingType.SUPPORT_RESISTANCE:
            levels = await self._generate_sr_levels()

        elif self.config.scaling_type == ScalingType.VOLUME_PROFILE:
            levels = await self._generate_volume_profile_levels()

        elif self.config.scaling_type == ScalingType.VWAP:
            levels = await self._generate_vwap_levels()

        elif self.config.scaling_type == ScalingType.TIME:
            levels = await self._generate_time_levels()

        elif self.config.scaling_type == ScalingType.PYRAMID:
            levels = await self._generate_pyramid_levels()

        elif self.config.scaling_type == ScalingType.MARTINGALE:
            levels = await self._generate_martingale_levels()

        elif self.config.scaling_type == ScalingType.FIBONACCI:
            levels = await self._generate_fibonacci_levels()

        # Filter and validate levels
        levels = self._filter_and_validate_levels(levels)

        return levels

    async def _generate_fixed_levels(self) -> List[ScalingLevel]:
        """Generate fixed price interval levels"""
        levels = []
        start = self.config.start_price
        end = self.config.end_price or start
        num_levels = self.config.number_of_levels

        if self.config.price_step:
            step = self.config.price_step
        else:
            step = abs(end - start) / num_levels

        for i in range(num_levels):
            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                price = start - (step * i)
            else:
                price = start + (step * i)

            size = self._calculate_level_size(i, num_levels)

            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.FIXED
            ))

        return levels

    async def _generate_percentage_levels(self) -> List[ScalingLevel]:
        """Generate percentage-based levels"""
        levels = []
        start = self.config.start_price
        percent_step = self.config.percent_step

        for i in range(self.config.number_of_levels):
            percent = percent_step * i

            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                price = start * (1 - percent / 100)
            else:
                price = start * (1 + percent / 100)

            size = self._calculate_level_size(i, self.config.number_of_levels)

            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.PERCENTAGE
            ))

        return levels

    async def _generate_atr_levels(self) -> List[ScalingLevel]:
        """Generate ATR-based levels"""
        levels = []
        start = self.config.start_price

        atr = self._calculate_atr()
        if atr is None:
            atr = start * 0.01

        step = atr * self.config.atr_multiplier

        for i in range(self.config.number_of_levels):
            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                price = start - (step * i)
            else:
                price = start + (step * i)

            size = self._calculate_level_size(i, self.config.number_of_levels)

            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.ATR
            ))

        return levels

    async def _generate_volatility_levels(self) -> List[ScalingLevel]:
        """Generate volatility-based levels"""
        levels = []
        start = self.config.start_price

        volatility = self._calculate_volatility()
        if volatility is None:
            volatility = 0.01

        # Wider spacing in high volatility
        step = start * volatility * self.config.volatility_multiplier

        for i in range(self.config.number_of_levels):
            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                price = start - (step * i)
            else:
                price = start + (step * i)

            size = self._calculate_level_size(i, self.config.number_of_levels)

            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.VOLATILITY
            ))

        return levels

    async def _generate_sr_levels(self) -> List[ScalingLevel]:
        """Generate support/resistance-based levels"""
        levels = []
        start = self.config.start_price

        # Find support and resistance levels
        supports, resistances = await self._find_sr_levels(start)

        if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
            price_levels = sorted(supports, reverse=True)[:self.config.number_of_levels]
            if len(price_levels) < self.config.number_of_levels:
                # Fill with calculated levels
                remaining = self.config.number_of_levels - len(price_levels)
                last_price = price_levels[-1] if price_levels else start
                step = last_price * 0.01
                for i in range(remaining):
                    price_levels.append(last_price - (step * (i + 1)))
        else:
            price_levels = sorted(resistances)[:self.config.number_of_levels]
            if len(price_levels) < self.config.number_of_levels:
                remaining = self.config.number_of_levels - len(price_levels)
                last_price = price_levels[-1] if price_levels else start
                step = last_price * 0.01
                for i in range(remaining):
                    price_levels.append(last_price + (step * (i + 1)))

        for i, price in enumerate(price_levels[:self.config.number_of_levels]):
            size = self._calculate_level_size(i, self.config.number_of_levels)
            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.SUPPORT_RESISTANCE
            ))

        return levels

    async def _generate_volume_profile_levels(self) -> List[ScalingLevel]:
        """Generate volume profile-based levels"""
        levels = []
        start = self.config.start_price

        if len(self._price_history) < self.config.volume_profile_window:
            return await self._generate_percentage_levels()

        # Calculate volume profile
        volume_profile = await self._calculate_volume_profile()

        # Find high volume nodes
        high_volume_nodes = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)

        if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
            nodes = [node for node, _ in high_volume_nodes if node < start]
        else:
            nodes = [node for node, _ in high_volume_nodes if node > start]

        if len(nodes) < self.config.number_of_levels:
            remaining = self.config.number_of_levels - len(nodes)
            step = start * 0.01
            last_node = nodes[-1] if nodes else start
            for i in range(remaining):
                if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                    nodes.append(last_node - (step * (i + 1)))
                else:
                    nodes.append(last_node + (step * (i + 1)))

        for i, price in enumerate(nodes[:self.config.number_of_levels]):
            size = self._calculate_level_size(i, self.config.number_of_levels)
            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.VOLUME_PROFILE
            ))

        return levels

    async def _generate_vwap_levels(self) -> List[ScalingLevel]:
        """Generate VWAP-based levels"""
        levels = []
        start = self.config.start_price

        vwap = self._calculate_vwap()
        if vwap is None:
            vwap = start

        # Generate levels around VWAP
        deviation = self.config.vwap_deviation

        for i in range(self.config.number_of_levels):
            factor = 1 + (i * deviation)

            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                price = vwap * (1 - (i / self.config.number_of_levels) * deviation)
            else:
                price = vwap * (1 + (i / self.config.number_of_levels) * deviation)

            size = self._calculate_level_size(i, self.config.number_of_levels)

            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.VWAP
            ))

        return levels

    async def _generate_time_levels(self) -> List[ScalingLevel]:
        """Generate time-based levels"""
        levels = []
        start = self.config.start_price

        if not self.config.time_interval:
            return await self._generate_percentage_levels()

        # Calculate price changes over time intervals
        price_changes = []

        for i in range(self.config.number_of_levels):
            # Look back at historical price changes
            if len(self._price_history) > self.config.number_of_levels:
                idx = -self.config.number_of_levels + i
                if idx < 0:
                    price_changes.append(0)
                else:
                    change = (self._price_history[idx] - self._price_history[idx - 1]) / self._price_history[idx - 1]
                    price_changes.append(change)
            else:
                price_changes.append(0)

        for i in range(self.config.number_of_levels):
            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                price = start * (1 + price_changes[i] * 2) if i > 0 else start
            else:
                price = start * (1 - price_changes[i] * 2) if i > 0 else start

            size = self._calculate_level_size(i, self.config.number_of_levels)

            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.TIME,
                expire_at=datetime.utcnow() + (self.config.time_interval * (i + 1))
            ))

        return levels

    async def _generate_pyramid_levels(self) -> List[ScalingLevel]:
        """Generate pyramid scaling levels"""
        levels = []
        start = self.config.start_price
        num_levels = self.config.number_of_levels

        # Pyramid scaling: smaller positions as price moves
        for i in range(num_levels):
            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                price = start * (1 - (i * 0.01))
            else:
                price = start * (1 + (i * 0.01))

            # Size decreases exponentially
            size_factor = 1 / (1 + i * 0.5)
            size = self.config.base_size * size_factor

            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.PYRAMID
            ))

        return levels

    async def _generate_martingale_levels(self) -> List[ScalingLevel]:
        """Generate martingale scaling levels"""
        levels = []
        start = self.config.start_price
        num_levels = min(self.config.number_of_levels, self.config.max_martingale_levels)

        for i in range(num_levels):
            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                price = start * (1 - (i * 0.01))
            else:
                price = start * (1 + (i * 0.01))

            # Size increases exponentially
            size = self.config.base_size * (self.config.martingale_multiplier ** i)

            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.MARTINGALE
            ))

        return levels

    async def _generate_fibonacci_levels(self) -> List[ScalingLevel]:
        """Generate Fibonacci-based scaling levels"""
        levels = []
        start = self.config.start_price

        for i, fib_level in enumerate(self.config.fibonacci_levels[:self.config.number_of_levels]):
            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                price = start * (1 - fib_level * 0.1)
            else:
                price = start * (1 + fib_level * 0.1)

            size = self._calculate_level_size(i, self.config.number_of_levels)

            levels.append(ScalingLevel(
                price=round_to_tick_size(price),
                size=size,
                size_percent=(size / self.config.total_size) * 100,
                priority=i + 1,
                type=ScalingType.FIBONACCI
            ))

        return levels

    def _calculate_level_size(self, level_index: int, total_levels: int) -> float:
        """Calculate size for a level based on mode"""
        if self.config.size_step:
            return min(self.config.base_size + (level_index * self.config.size_step), self.config.max_size_per_level or float('inf'))

        if self.config.mode == ScalingMode.LINEAR:
            return self.config.total_size / total_levels

        elif self.config.mode == ScalingMode.LOGARITHMIC:
            weight = 1 / (level_index + 1)
            total_weight = sum(1 / (i + 1) for i in range(total_levels))
            return (weight / total_weight) * self.config.total_size

        elif self.config.mode == ScalingMode.EXPONENTIAL:
            weight = 2 ** level_index
            total_weight = sum(2 ** i for i in range(total_levels))
            return (weight / total_weight) * self.config.total_size

        elif self.config.mode == ScalingMode.ADAPTIVE:
            # Adaptive based on market conditions
            volatility = self._calculate_volatility()
            if volatility is None:
                volatility = 0.01
            weight = 1 / (1 + volatility * level_index)
            total_weight = sum(1 / (1 + volatility * i) for i in range(total_levels))
            return (weight / total_weight) * self.config.total_size

        elif self.config.mode == ScalingMode.DCA:
            return self.config.total_size / total_levels

        elif self.config.mode == ScalingMode.PYRAMID:
            weight = 1 / (level_index + 1)
            total_weight = sum(1 / (i + 1) for i in range(total_levels))
            return (weight / total_weight) * self.config.total_size

        elif self.config.mode == ScalingMode.REVERSE:
            weight = 1 / (total_levels - level_index)
            total_weight = sum(1 / (total_levels - i) for i in range(total_levels))
            return (weight / total_weight) * self.config.total_size

        return self.config.total_size / total_levels

    def _filter_and_validate_levels(self, levels: List[ScalingLevel]) -> List[ScalingLevel]:
        """Filter and validate scaling levels"""
        validated = []
        total_size = 0

        # Sort by priority
        levels.sort(key=lambda x: x.priority)

        for level in levels:
            # Validate price
            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                if level.price > self.config.start_price:
                    continue
            else:
                if level.price < self.config.start_price:
                    continue

            # Validate size
            if level.size <= 0:
                continue

            # Apply min/max limits
            if self.config.min_level_distance:
                if validated and abs(level.price - validated[-1].price) < self.config.min_level_distance:
                    continue

            if self.config.max_level_distance:
                if validated and abs(level.price - validated[-1].price) > self.config.max_level_distance:
                    continue

            validated.append(level)
            total_size += level.size

        # Normalize sizes to match total_size
        if total_size > 0 and total_size != self.config.total_size:
            for level in validated:
                level.size = (level.size / total_size) * self.config.total_size
                level.size_percent = (level.size / self.config.total_size) * 100

        return validated    async def _submit_orders(self):
        """Submit orders for all levels"""
        if not self._broker:
            return

        for level_index, level in enumerate(self._levels):
            try:
                order_params = {
                    'symbol': self.config.symbol,
                    'side': OrderSide.BUY if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH] else OrderSide.SELL,
                    'quantity': level.size,
                    'order_type': level.order_type,
                    'time_in_force': level.time_in_force,
                    'client_order_id': f"{self.id}_{level_index}"
                }

                if level.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                    order_params['price'] = level.price
                if level.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                    order_params['stop_price'] = level.stop_price or level.price

                result = await self._broker.place_order(**order_params)
                self._order_ids[level_index] = result.get('order_id')

                logger.debug(f"Submitted order for level {level_index} at {level.price}")

            except Exception as e:
                logger.error(f"Failed to submit order for level {level_index}: {e}")

    async def _check_levels(self, current_price: float) -> bool:
        """Check if any levels should be executed"""
        triggered = False

        for level_index, level in enumerate(self._levels):
            if level_index in self._executed_levels:
                continue

            order_id = self._order_ids.get(level_index)
            if not order_id:
                continue

            try:
                status = await self._broker.get_order_status(order_id)

                if status.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                    await self._execute_level(level_index, level, status)
                    triggered = True

                elif status.get('status') in ['REJECTED', 'EXPIRED']:
                    # Re-submit failed order
                    await self._resubmit_order(level_index, level)

            except Exception as e:
                logger.error(f"Failed to check order {order_id}: {e}")

        return triggered

    async def _execute_level(self, level_index: int, level: ScalingLevel, status: Dict[str, Any]):
        """Execute a scaling level"""
        filled_size = status.get('filled_quantity', level.size)
        exec_price = status.get('price', level.price)

        # Update metrics
        self._filled_size += filled_size
        self._remaining_size -= filled_size
        self._total_cost += filled_size * exec_price

        if self._filled_size > 0:
            self._average_price = self._total_cost / self._filled_size

        self._executed_levels.append(level_index)
        self._metrics.levels_executed += 1
        self._metrics.filled_size = self._filled_size
        self._metrics.remaining_size = self._remaining_size
        self._metrics.average_price = self._average_price

        logger.info(f"Level {level_index} executed at {exec_price}, size: {filled_size}")

        # Check if all levels executed
        if len(self._executed_levels) == len(self._levels):
            self._state = 'EXECUTED'
            logger.info(f"Scaling order {self.id} fully executed")

    async def _resubmit_order(self, level_index: int, level: ScalingLevel):
        """Resubmit a failed order"""
        try:
            order_params = {
                'symbol': self.config.symbol,
                'side': OrderSide.BUY if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH] else OrderSide.SELL,
                'quantity': level.size,
                'order_type': level.order_type,
                'time_in_force': level.time_in_force,
                'client_order_id': f"{self.id}_{level_index}_retry"
            }

            if level.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                order_params['price'] = level.price
            if level.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                order_params['stop_price'] = level.stop_price or level.price

            result = await self._broker.place_order(**order_params)
            self._order_ids[level_index] = result.get('order_id')

            logger.debug(f"Resubmitted order for level {level_index}")

        except Exception as e:
            logger.error(f"Failed to resubmit order for level {level_index}: {e}")

    def _update_metrics(self, current_price: float):
        """Update metrics"""
        if self._filled_size > 0:
            # Calculate unrealized P&L
            avg_price = self._average_price or current_price
            if self.config.scaling_direction in [ScalingDirection.BUY, ScalingDirection.BOTH]:
                self._metrics.unrealized_pnl = (current_price - avg_price) * self._filled_size
            else:
                self._metrics.unrealized_pnl = (avg_price - current_price) * self._filled_size

        self._metrics.total_pnl = self._metrics.realized_pnl + self._metrics.unrealized_pnl

        # Calculate drawdown
        if self._metrics.total_pnl < 0:
            self._metrics.max_drawdown = min(self._metrics.max_drawdown, self._metrics.total_pnl)
        else:
            self._metrics.max_runup = max(self._metrics.max_runup, self._metrics.total_pnl)

        # Calculate fill rate
        if self.config.total_size > 0:
            self._metrics.fill_rate = (self._filled_size / self.config.total_size) * 100

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

    def _calculate_vwap(self) -> Optional[float]:
        """Calculate VWAP from price history"""
        if len(self._price_history) < self.config.vwap_period:
            return None

        total_volume = sum(self._volume_history[-self.config.vwap_period:]) if self._volume_history else len(self._price_history)
        if total_volume == 0:
            return None

        total_value = 0
        for i in range(-self.config.vwap_period, 0):
            price = self._price_history[i]
            volume = self._volume_history[i] if i < len(self._volume_history) else 1
            total_value += price * volume

        return total_value / total_volume

    async def _calculate_volume_profile(self) -> Dict[float, float]:
        """Calculate volume profile"""
        profile = {}

        if len(self._price_history) < self.config.volume_profile_window:
            return profile

        prices = self._price_history[-self.config.volume_profile_window:]
        volumes = self._volume_history[-self.config.volume_profile_window:] if self._volume_history else [1] * len(prices)

        # Group prices into buckets
        min_price = min(prices)
        max_price = max(prices)
        bucket_size = (max_price - min_price) / 20  # 20 buckets

        for price, volume in zip(prices, volumes):
            bucket = round(price / bucket_size) * bucket_size
            profile[bucket] = profile.get(bucket, 0) + volume

        return profile

    async def _find_sr_levels(self, price: float) -> tuple:
        """Find support and resistance levels"""
        supports = []
        resistances = []

        if len(self._price_history) < 20:
            return supports, resistances

        # Simple support/resistance detection
        for i in range(10, len(self._price_history) - 10):
            # Check for support
            if (self._price_history[i] <= self._price_history[i-1] and
                self._price_history[i] <= self._price_history[i-2] and
                self._price_history[i] <= self._price_history[i+1] and
                self._price_history[i] <= self._price_history[i+2]):
                if self._price_history[i] < price:
                    supports.append(self._price_history[i])

            # Check for resistance
            if (self._price_history[i] >= self._price_history[i-1] and
                self._price_history[i] >= self._price_history[i-2] and
                self._price_history[i] >= self._price_history[i+1] and
                self._price_history[i] >= self._price_history[i+2]):
                if self._price_history[i] > price:
                    resistances.append(self._price_history[i])

        return supports, resistances

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
        """Convert scaling order to dictionary"""
        return {
            'id': self.id,
            'state': self._state,
            'config': self.config.model_dump(),
            'metrics': self._metrics.model_dump(),
            'current_price': self._current_price,
            'levels': [level.model_dump() for level in self._levels],
            'executed_levels': self._executed_levels,
            'order_ids': self._order_ids,
            'filled_size': self._filled_size,
            'remaining_size': self._remaining_size,
            'average_price': self._average_price,
            'total_cost': self._total_cost
        }

    @classmethod
    async def from_dict(
        cls,
        data: Dict[str, Any],
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ) -> 'ScalingOrder':
        """Create scaling order from dictionary"""
        config = ScalingOrderConfig(**data.get('config', {}))
        scaling_order = cls(config=config, broker=broker, order_manager=order_manager)

        # Restore state
        scaling_order._state = data.get('state', 'INACTIVE')
        scaling_order._current_price = data.get('current_price')
        scaling_order._filled_size = data.get('filled_size', 0.0)
        scaling_order._remaining_size = data.get('remaining_size', 0.0)
        scaling_order._average_price = data.get('average_price', 0.0)
        scaling_order._total_cost = data.get('total_cost', 0.0)
        scaling_order._executed_levels = data.get('executed_levels', [])

        # Restore levels
        if data.get('levels'):
            scaling_order._levels = [ScalingLevel(**level) for level in data.get('levels')]

        # Restore order IDs
        if data.get('order_ids'):
            scaling_order._order_ids = {int(k): v for k, v in data.get('order_ids').items()}

        # Restore metrics
        if data.get('metrics'):
            scaling_order._metrics = ScalingMetrics(**data.get('metrics'))

        return scaling_order

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cancel()
        await self.stop_price_monitoring()
