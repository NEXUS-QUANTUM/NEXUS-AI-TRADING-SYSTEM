"""
NEXUS AI TRADING SYSTEM - Conditional Order Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/conditional_order.py
Version: 1.0.0
Description: Advanced conditional order implementation with full API integration
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable, Tuple, Set
from collections import deque
import math

from pydantic import BaseModel, Field, ConfigDict, validator, root_validator

from shared.types.trading import OrderSide, OrderType, OrderStatus, TimeInForce
from shared.helpers.trading_helpers import (
    calculate_percentage_change,
    calculate_price_distance,
    round_to_tick_size,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands
)
from shared.constants.trading_constants import (
    MIN_ORDER_SIZE,
    MAX_CONDITIONAL_ORDERS,
    CONDITION_CHECK_INTERVAL
)
from shared.interfaces.broker import BrokerInterface
from shared.utilities.logger import get_logger

from trading.smart_orders.base_order import SmartOrder, SmartOrderConfig
from trading.smart_orders.order_manager import OrderManager

logger = get_logger(__name__)


class ConditionType(str, Enum):
    """Types of conditions"""
    PRICE = "price"                      # Price condition
    PERCENTAGE = "percentage"            # Percentage change condition
    TIME = "time"                        # Time-based condition
    VOLUME = "volume"                    # Volume condition
    INDICATOR = "indicator"              # Technical indicator condition
    COMPOSITE = "composite"              # Composite condition
    EVENT = "event"                      # Event-based condition
    NEWS = "news"                        # News-based condition
    POSITION = "position"                # Position-based condition
    PORTFOLIO = "portfolio"              # Portfolio-based condition
    CUSTOM = "custom"                    # Custom condition


class ComparisonOperator(str, Enum):
    """Comparison operators"""
    EQUAL = "=="
    NOT_EQUAL = "!="
    GREATER = ">"
    GREATER_EQUAL = ">="
    LESS = "<"
    LESS_EQUAL = "<="
    BETWEEN = "between"
    NOT_BETWEEN = "not_between"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"


class LogicalOperator(str, Enum):
    """Logical operators for compound conditions"""
    AND = "and"
    OR = "or"
    NOT = "not"
    XOR = "xor"


class IndicatorType(str, Enum):
    """Technical indicator types"""
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER = "bollinger"
    SMA = "sma"
    EMA = "ema"
    ATR = "atr"
    STOCH = "stoch"
    WILLIAMS = "williams"
    CCI = "cci"
    ADX = "adx"
    OBV = "obv"
    CUSTOM = "custom"


class TimeCondition(str, Enum):
    """Time-based conditions"""
    BEFORE = "before"
    AFTER = "after"
    BETWEEN = "between"
    DURING = "during"
    NOT_DURING = "not_during"
    AT = "at"


class Condition(BaseModel):
    """Individual condition definition"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    condition_type: ConditionType = Field(..., description="Type of condition")
    variable: Optional[str] = Field(None, description="Variable to check")
    operator: ComparisonOperator = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")
    value2: Optional[Any] = Field(None, description="Second value for between operators")
    
    # Indicator-specific
    indicator_type: Optional[IndicatorType] = Field(None, description="Indicator type")
    indicator_params: Dict[str, Any] = Field(default_factory=dict, description="Indicator parameters")
    indicator_value: Optional[float] = Field(None, description="Indicator value")
    
    # Time-specific
    time_value: Optional[str] = Field(None, description="Time value")
    time_start: Optional[str] = Field(None, description="Start time")
    time_end: Optional[str] = Field(None, description="End time")
    timezone: str = Field("UTC", description="Timezone")
    
    # Event-specific
    event_type: Optional[str] = Field(None, description="Event type")
    event_data: Optional[Dict[str, Any]] = Field(None, description="Event data")
    
    # Custom-specific
    custom_function: Optional[str] = Field(None, description="Custom function name")
    custom_params: Dict[str, Any] = Field(default_factory=dict, description="Custom parameters")
    
    # Additional
    description: Optional[str] = Field(None, description="Condition description")
    enabled: bool = Field(True, description="Whether condition is enabled")


class CompoundCondition(BaseModel):
    """Compound condition combining multiple conditions"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    logical_operator: LogicalOperator = Field(..., description="Logical operator")
    conditions: List[Union[Condition, 'CompoundCondition']] = Field(..., description="Sub-conditions")
    description: Optional[str] = Field(None, description="Condition description")
    enabled: bool = Field(True, description="Whether condition is enabled")

    @root_validator(pre=True)
    def validate_conditions(cls, values):
        conditions = values.get('conditions', [])
        if not conditions:
            raise ValueError("Compound condition must have at least one sub-condition")
        return values


class ConditionalActionType(str, Enum):
    """Types of actions to execute"""
    PLACE_ORDER = "place_order"
    CANCEL_ORDER = "cancel_order"
    MODIFY_ORDER = "modify_order"
    CLOSE_POSITION = "close_position"
    SEND_ALERT = "send_alert"
    EXECUTE_SCRIPT = "execute_script"
    WEBHOOK = "webhook"
    NOTIFY = "notify"
    NONE = "none"


class ConditionalAction(BaseModel):
    """Action to execute when conditions are met"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    action_type: ConditionalActionType = Field(..., description="Action type")
    order_id: Optional[str] = Field(None, description="Order ID for order actions")
    
    # Order parameters
    symbol: Optional[str] = Field(None, description="Trading symbol")
    side: Optional[OrderSide] = Field(None, description="Order side")
    order_type: Optional[OrderType] = Field(None, description="Order type")
    size: Optional[float] = Field(None, description="Order size")
    price: Optional[float] = Field(None, description="Order price")
    stop_price: Optional[float] = Field(None, description="Stop price")
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    
    # Alert parameters
    alert_message: Optional[str] = Field(None, description="Alert message")
    alert_level: str = Field("info", description="Alert level")
    
    # Webhook parameters
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    webhook_payload: Optional[Dict[str, Any]] = Field(None, description="Webhook payload")
    
    # Script parameters
    script_path: Optional[str] = Field(None, description="Script path")
    script_args: List[str] = Field(default_factory=list, description="Script arguments")
    
    # Notification parameters
    notification_channel: Optional[str] = Field(None, description="Notification channel")
    notification_message: Optional[str] = Field(None, description="Notification message")
    
    # General
    retry_count: int = Field(3, description="Number of retries")
    retry_delay: float = Field(1.0, description="Retry delay in seconds")
    description: Optional[str] = Field(None, description="Action description")


class ConditionalOrderConfig(SmartOrderConfig):
    """Configuration for conditional order"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    name: str = Field(..., description="Conditional order name")
    symbol: str = Field(..., description="Trading symbol")
    
    # Conditions
    condition: Union[Condition, CompoundCondition] = Field(..., description="Condition to evaluate")
    check_interval: float = Field(CONDITION_CHECK_INTERVAL, description="Check interval in seconds")
    check_count: int = Field(1, description="Number of consecutive checks needed")
    
    # Actions
    action_on_true: ConditionalAction = Field(..., description="Action when condition is true")
    action_on_false: Optional[ConditionalAction] = Field(None, description="Action when condition is false")
    
    # Time constraints
    start_time: Optional[datetime] = Field(None, description="Start time for condition checking")
    end_time: Optional[datetime] = Field(None, description="End time for condition checking")
    active_days: List[int] = Field(default_factory=list, description="Active days of week (0-6)")
    
    # Execution limits
    max_executions: int = Field(1, description="Maximum number of executions")
    execution_count: int = Field(0, description="Number of times executed")
    cooldown_period: Optional[float] = Field(None, description="Cooldown period in seconds")
    
    # Order parameters
    order_type: OrderType = Field(default=OrderType.LIMIT)
    order_size: Optional[float] = Field(None, description="Order size")
    order_price: Optional[float] = Field(None, description="Order price")
    order_stop_price: Optional[float] = Field(None, description="Order stop price")
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    
    # Risk management
    max_loss: Optional[float] = Field(None, description="Maximum loss allowed")
    max_position_size: Optional[float] = Field(None, description="Maximum position size")
    require_confirmation: bool = Field(False, description="Require manual confirmation")
    
    # Persistence
    persist_state: bool = Field(True, description="Persist state across restarts")

    @validator('check_count')
    def validate_check_count(cls, v):
        if v < 1:
            raise ValueError("Check count must be at least 1")
        return v

    @validator('max_executions')
    def validate_max_executions(cls, v):
        if v < 1:
            raise ValueError("Max executions must be at least 1")
        return v

    @validator('active_days')
    def validate_active_days(cls, v):
        for day in v:
            if day < 0 or day > 6:
                raise ValueError("Active days must be between 0 and 6")
        return v


class ConditionalState(str, Enum):
    """States of a conditional order"""
    PENDING = "pending"                  # Waiting to be activated
    ACTIVE = "active"                    # Monitoring conditions
    TRIGGERED = "triggered"              # Condition met
    EXECUTED = "executed"                # Action executed
    COMPLETED = "completed"              # Fully completed
    CANCELLED = "cancelled"              # Cancelled
    EXPIRED = "expired"                  # Expired
    COOLDOWN = "cooldown"                # In cooldown period


class ConditionHistory(BaseModel):
    """History of condition evaluations"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    condition_met: bool
    values: Dict[str, Any] = Field(default_factory=dict)
    details: str = ""


class ConditionalMetrics(BaseModel):
    """Metrics for conditional order"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_checks: int = Field(0, description="Total condition checks")
    true_checks: int = Field(0, description="Checks where condition was true")
    false_checks: int = Field(0, description="Checks where condition was false")
    
    executions: int = Field(0, description="Number of executions")
    successful_executions: int = Field(0, description="Successful executions")
    failed_executions: int = Field(0, description="Failed executions")
    
    avg_check_time: float = Field(0.0, description="Average check time in seconds")
    last_check_time: Optional[datetime] = Field(None, description="Last check timestamp")
    first_check_time: Optional[datetime] = Field(None, description="First check timestamp")
    
    history: List[ConditionHistory] = Field(default_factory=list, description="Condition history")
    max_history: int = Field(100, description="Maximum history entries")


class ConditionalOrder(SmartOrder):
    """
    Advanced conditional order implementation with full API integration.
    
    Features:
    - Multiple condition types (price, percentage, time, volume, indicators, etc.)
    - Compound conditions with logical operators (AND, OR, NOT, XOR)
    - Technical indicator conditions (RSI, MACD, Bollinger Bands, etc.)
    - Time-based conditions
    - Event-based conditions
    - Custom conditions
    - Multiple action types
    - Execution limits and cooldown
    - Full broker API integration
    - Performance metrics tracking
    """

    def __init__(
        self,
        config: ConditionalOrderConfig,
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ):
        """
        Initialize conditional order.

        Args:
            config: Conditional order configuration
            broker: Optional broker interface
            order_manager: Optional order manager
        """
        super().__init__(config=config, broker=broker, order_manager=order_manager)
        self.config = config
        self._metrics = ConditionalMetrics()
        self._state = ConditionalState.PENDING
        self._current_price: Optional[float] = None
        self._consecutive_checks: int = 0
        self._last_execution_time: Optional[datetime] = None
        self._triggered: bool = False
        self._executed: bool = False
        self._check_count: int = 0
        
        # Price history for indicators
        self._price_history: List[float] = []
        self._volume_history: List[float] = []
        self._timestamp_history: List[datetime] = []
        self._max_history_length = 1000
        
        # Indicator cache
        self._indicator_cache: Dict[str, Any] = {}
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        # Control flags
        self._running: bool = False
        self._check_task: Optional[asyncio.Task] = None
        self._subscription_id: Optional[str] = None
        
        # Custom functions
        self._custom_functions: Dict[str, Callable] = {}
        
        # Locks
        self._state_lock = asyncio.Lock()
        self._history_lock = asyncio.Lock()

        logger.info(f"Initialized ConditionalOrder: {config.name} (ID: {self.id})")

    async def activate(self, price: Optional[float] = None) -> bool:
        """
        Activate the conditional order.

        Args:
            price: Optional current price

        Returns:
            bool: True if activated successfully
        """
        async with self._state_lock:
            if self._state not in [ConditionalState.PENDING, ConditionalState.COOLDOWN]:
                logger.warning(f"Conditional order {self.id} cannot be activated from state {self._state}")
                return False

            self._current_price = price or self._current_price

            # Set initial state
            self._state = ConditionalState.ACTIVE
            self._running = True
            self._check_count = 0
            self._consecutive_checks = 0
            self._triggered = False
            self._executed = False
            
            if not self._metrics.first_check_time:
                self._metrics.first_check_time = datetime.utcnow()

            # Start check task
            self._check_task = asyncio.create_task(self._check_loop())

            logger.info(f"Conditional order {self.config.name} activated")
            return True

    async def update_price(self, new_price: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Update current price.

        Args:
            new_price: Current market price
            timestamp: Optional timestamp

        Returns:
            bool: True if updated
        """
        self._current_price = new_price

        # Update price history
        self._price_history.append(new_price)
        self._timestamp_history.append(timestamp or datetime.utcnow())
        if len(self._price_history) > self._max_history_length:
            self._price_history.pop(0)
            self._timestamp_history.pop(0)

        return True

    async def check_conditions(self, price: Optional[float] = None) -> bool:
        """
        Manually check conditions.

        Args:
            price: Current price

        Returns:
            bool: True if conditions met
        """
        if self._state not in [ConditionalState.ACTIVE, ConditionalState.COOLDOWN]:
            return False

        check_price = price or self._current_price
        if check_price is None:
            return False

        return await self._evaluate_condition()

    async def cancel(self) -> bool:
        """
        Cancel the conditional order.

        Returns:
            bool: True if cancelled successfully
        """
        async with self._state_lock:
            if self._state in [ConditionalState.CANCELLED, ConditionalState.COMPLETED]:
                return False

            self._state = ConditionalState.CANCELLED
            self._running = False

            if self._check_task:
                self._check_task.cancel()

            logger.info(f"Conditional order {self.config.name} cancelled")
            return True

    async def get_metrics(self) -> ConditionalMetrics:
        """Get current metrics"""
        async with self._history_lock:
            return self._metrics.model_copy()

    def get_state(self) -> str:
        """Get current state"""
        return self._state.value

    def get_triggered(self) -> bool:
        """Check if condition has been triggered"""
        return self._triggered

    def get_executed(self) -> bool:
        """Check if action has been executed"""
        return self._executed

    async def register_custom_function(self, name: str, func: Callable):
        """
        Register a custom function for custom conditions.

        Args:
            name: Function name
            func: Callable function
        """
        self._custom_functions[name] = func
        logger.debug(f"Registered custom function: {name}")

    async def register_event_handler(self, event_type: str, handler: Callable):
        """
        Register an event handler.

        Args:
            event_type: Event type
            handler: Handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug(f"Registered event handler for {event_type}")

    async def _check_loop(self):
        """Main check loop"""
        while self._running:
            try:
                # Check if we should evaluate
                if await self._should_evaluate():
                    start_time = time.time()

                    # Evaluate condition
                    condition_met = await self._evaluate_condition()

                    # Update metrics
                    check_time = time.time() - start_time
                    self._metrics.avg_check_time = (
                        (self._metrics.avg_check_time * self._metrics.total_checks + check_time) /
                        (self._metrics.total_checks + 1)
                    )
                    self._metrics.total_checks += 1
                    self._metrics.last_check_time = datetime.utcnow()

                    if condition_met:
                        self._metrics.true_checks += 1
                        self._consecutive_checks += 1
                    else:
                        self._metrics.false_checks += 1
                        self._consecutive_checks = 0

                    # Check if we should trigger
                    if condition_met and self._consecutive_checks >= self.config.check_count:
                        await self._trigger_action()

                    # Check cooldown
                    elif not condition_met and self._state == ConditionalState.COOLDOWN:
                        await self._check_cooldown()

                await asyncio.sleep(self.config.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in check loop: {e}")
                await asyncio.sleep(self.config.check_interval)

    async def _should_evaluate(self) -> bool:
        """Check if conditions should be evaluated"""
        # Check state
        if self._state not in [ConditionalState.ACTIVE, ConditionalState.COOLDOWN]:
            return False

        # Check execution limit
        if self.config.execution_count >= self.config.max_executions:
            self._state = ConditionalState.COMPLETED
            self._running = False
            return False

        # Check time constraints
        now = datetime.utcnow()

        if self.config.start_time and now < self.config.start_time:
            return False

        if self.config.end_time and now > self.config.end_time:
            self._state = ConditionalState.EXPIRED
            self._running = False
            return False

        if self.config.active_days:
            if now.weekday() not in self.config.active_days:
                return False

        # Check cooldown
        if self._state == ConditionalState.COOLDOWN:
            if self.config.cooldown_period:
                elapsed = (now - self._last_execution_time).total_seconds()
                if elapsed < self.config.cooldown_period:
                    return False
                else:
                    # Cooldown complete, resume active state
                    self._state = ConditionalState.ACTIVE
            else:
                self._state = ConditionalState.ACTIVE

        return True

    async def _evaluate_condition(self) -> bool:
        """Evaluate the condition"""
        try:
            # Update market data
            await self._update_market_data()

            # Evaluate condition
            if isinstance(self.config.condition, CompoundCondition):
                result = await self._evaluate_compound_condition(self.config.condition)
            else:
                result = await self._evaluate_single_condition(self.config.condition)

            # Record history
            async with self._history_lock:
                history = ConditionHistory(
                    condition_met=result,
                    values={
                        'price': self._current_price,
                        'timestamp': datetime.utcnow()
                    },
                    details=f"Check {self._check_count + 1}"
                )
                self._metrics.history.append(history)
                if len(self._metrics.history) > self._metrics.max_history:
                    self._metrics.history.pop(0)

            self._check_count += 1

            return result

        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False

    async def _evaluate_single_condition(self, condition: Condition) -> bool:
        """Evaluate a single condition"""
        if not condition.enabled:
            return False

        # Get the value based on condition type
        value = await self._get_condition_value(condition)

        if value is None:
            return False

        # Evaluate based on operator
        return self._compare_values(value, condition.operator, condition.value, condition.value2)

    async def _evaluate_compound_condition(self, compound: CompoundCondition) -> bool:
        """Evaluate a compound condition"""
        if not compound.enabled:
            return False

        results = []
        for cond in compound.conditions:
            if isinstance(cond, CompoundCondition):
                result = await self._evaluate_compound_condition(cond)
            else:
                result = await self._evaluate_single_condition(cond)
            results.append(result)

        # Apply logical operator
        if compound.logical_operator == LogicalOperator.AND:
            return all(results)
        elif compound.logical_operator == LogicalOperator.OR:
            return any(results)
        elif compound.logical_operator == LogicalOperator.NOT:
            return not results[0] if results else True
        elif compound.logical_operator == LogicalOperator.XOR:
            return sum(results) == 1

        return False

    async def _get_condition_value(self, condition: Condition) -> Any:
        """Get the value for a condition"""
        if condition.condition_type == ConditionType.PRICE:
            return self._current_price

        elif condition.condition_type == ConditionType.PERCENTAGE:
            if self._price_history:
                return calculate_percentage_change(self._price_history[-1], self._price_history[0])
            return 0.0

        elif condition.condition_type == ConditionType.VOLUME:
            if self._volume_history:
                return self._volume_history[-1] if self._volume_history else 0
            return 0.0

        elif condition.condition_type == ConditionType.INDICATOR:
            return await self._get_indicator_value(condition)

        elif condition.condition_type == ConditionType.TIME:
            return await self._get_time_value(condition)

        elif condition.condition_type == ConditionType.EVENT:
            return await self._get_event_value(condition)

        elif condition.condition_type == ConditionType.POSITION:
            return await self._get_position_value(condition)

        elif condition.condition_type == ConditionType.PORTFOLIO:
            return await self._get_portfolio_value(condition)

        elif condition.condition_type == ConditionType.CUSTOM:
            return await self._get_custom_value(condition)

        return None

    async def _get_indicator_value(self, condition: Condition) -> Optional[float]:
        """Calculate indicator value"""
        indicator_type = condition.indicator_type or IndicatorType.RSI
        params = condition.indicator_params

        if indicator_type == IndicatorType.RSI:
            period = params.get('period', 14)
            return self._calculate_rsi(period)

        elif indicator_type == IndicatorType.MACD:
            fast = params.get('fast', 12)
            slow = params.get('slow', 26)
            signal = params.get('signal', 9)
            return self._calculate_macd(fast, slow, signal)

        elif indicator_type == IndicatorType.BOLLINGER:
            period = params.get('period', 20)
            std_dev = params.get('std_dev', 2)
            band = params.get('band', 'middle')  # upper, middle, lower
            bb = self._calculate_bollinger_bands(period, std_dev)
            if band == 'upper':
                return bb['upper']
            elif band == 'lower':
                return bb['lower']
            else:
                return bb['middle']

        elif indicator_type == IndicatorType.SMA:
            period = params.get('period', 20)
            return self._calculate_sma(period)

        elif indicator_type == IndicatorType.EMA:
            period = params.get('period', 20)
            return self._calculate_ema(period)

        elif indicator_type == IndicatorType.ATR:
            period = params.get('period', 14)
            return self._calculate_atr(period)

        elif indicator_type == IndicatorType.STOCH:
            k_period = params.get('k_period', 14)
            d_period = params.get('d_period', 3)
            return self._calculate_stochastic(k_period, d_period)

        elif indicator_type == IndicatorType.WILLIAMS:
            period = params.get('period', 14)
            return self._calculate_williams(period)

        elif indicator_type == IndicatorType.CCI:
            period = params.get('period', 20)
            return self._calculate_cci(period)

        elif indicator_type == IndicatorType.ADX:
            period = params.get('period', 14)
            return self._calculate_adx(period)

        elif indicator_type == IndicatorType.OBV:
            return self._calculate_obv()

        return None

    async def _get_time_value(self, condition: Condition) -> Any:
        """Get time-based value"""
        now = datetime.utcnow()

        if condition.time_value:
            try:
                dt = datetime.fromisoformat(condition.time_value)
                return dt
            except ValueError:
                # Try parsing time string
                try:
                    dt = datetime.strptime(condition.time_value, "%H:%M:%S")
                    # Use today's date
                    return dt.replace(year=now.year, month=now.month, day=now.day)
                except ValueError:
                    return now

        return now

    async def _get_event_value(self, condition: Condition) -> bool:
        """Get event-based value"""
        # Check if event has occurred
        return condition.event_type in self._event_handlers

    async def _get_position_value(self, condition: Condition) -> Optional[float]:
        """Get position value"""
        if not self._broker:
            return None

        try:
            position = await self._broker.get_position(self.config.symbol)
            if position:
                return position.get('size', 0)
        except Exception:
            pass
        return 0.0

    async def _get_portfolio_value(self, condition: Condition) -> Optional[float]:
        """Get portfolio value"""
        if not self._broker:
            return None

        try:
            portfolio = await self._broker.get_portfolio()
            if portfolio:
                return portfolio.get('total_value', 0)
        except Exception:
            pass
        return 0.0

    async def _get_custom_value(self, condition: Condition) -> Any:
        """Get custom function value"""
        if condition.custom_function in self._custom_functions:
            try:
                func = self._custom_functions[condition.custom_function]
                if asyncio.iscoroutinefunction(func):
                    return await func(**condition.custom_params)
                else:
                    return func(**condition.custom_params)
            except Exception as e:
                logger.error(f"Error in custom function {condition.custom_function}: {e}")
        return None

    def _compare_values(self, value: Any, operator: ComparisonOperator, compare_value: Any, value2: Any = None) -> bool:
        """Compare values based on operator"""
        try:
            if operator == ComparisonOperator.EQUAL:
                return value == compare_value
            elif operator == ComparisonOperator.NOT_EQUAL:
                return value != compare_value
            elif operator == ComparisonOperator.GREATER:
                return value > compare_value
            elif operator == ComparisonOperator.GREATER_EQUAL:
                return value >= compare_value
            elif operator == ComparisonOperator.LESS:
                return value < compare_value
            elif operator == ComparisonOperator.LESS_EQUAL:
                return value <= compare_value
            elif operator == ComparisonOperator.BETWEEN:
                return compare_value <= value <= value2 if value2 is not None else False
            elif operator == ComparisonOperator.NOT_BETWEEN:
                return value < compare_value or value > value2 if value2 is not None else False
            elif operator == ComparisonOperator.CROSSES_ABOVE:
                return self._check_cross_above(value, compare_value)
            elif operator == ComparisonOperator.CROSSES_BELOW:
                return self._check_cross_below(value, compare_value)
        except Exception as e:
            logger.error(f"Error comparing values: {e}")
            return False

        return False

    def _check_cross_above(self, current: float, level: float) -> bool:
        """Check if current value crosses above a level"""
        if len(self._price_history) < 2:
            return False
        previous = self._price_history[-2]
        return previous <= level < current

    def _check_cross_below(self, current: float, level: float) -> bool:
        """Check if current value crosses below a level"""
        if len(self._price_history) < 2:
            return False
        previous = self._price_history[-2]
        return previous >= level > current

    def _calculate_rsi(self, period: int) -> Optional[float]:
        """Calculate RSI"""
        if len(self._price_history) < period + 1:
            return None

        gains = 0
        losses = 0

        for i in range(-period, 0):
            change = self._price_history[i] - self._price_history[i-1]
            if change > 0:
                gains += change
            else:
                losses -= change

        if losses == 0:
            return 100.0

        rs = gains / losses
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, fast: int, slow: int, signal: int) -> Optional[Dict[str, float]]:
        """Calculate MACD"""
        if len(self._price_history) < slow + signal:
            return None

        fast_ema = self._calculate_ema(fast)
        slow_ema = self._calculate_ema(slow)

        if fast_ema is None or slow_ema is None:
            return None

        macd_line = fast_ema - slow_ema

        # Calculate signal line (EMA of MACD)
        macd_values = []
        for i in range(-signal, 0):
            f_ema = self._calculate_ema(fast, offset=i)
            s_ema = self._calculate_ema(slow, offset=i)
            if f_ema is not None and s_ema is not None:
                macd_values.append(f_ema - s_ema)

        if len(macd_values) < signal:
            return None

        signal_line = sum(macd_values[-signal:]) / signal
        histogram = macd_line - signal_line

        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }

    def _calculate_bollinger_bands(self, period: int, std_dev: float) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        middle = self._calculate_sma(period) or 0
        if len(self._price_history) < period:
            return {'upper': middle, 'middle': middle, 'lower': middle}

        # Calculate standard deviation
        values = self._price_history[-period:]
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = math.sqrt(variance)

        return {
            'upper': middle + (std * std_dev),
            'middle': middle,
            'lower': middle - (std * std_dev)
        }

    def _calculate_sma(self, period: int, offset: int = 0) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if len(self._price_history) < period + abs(offset):
            return None

        start = -period + offset if offset < 0 else -period
        end = offset if offset < 0 else -offset
        values = self._price_history[start:end] if offset != 0 else self._price_history[-period:]

        if not values:
            return None

        return sum(values) / len(values)

    def _calculate_ema(self, period: int, offset: int = 0) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(self._price_history) < period + abs(offset):
            return None

        multiplier = 2 / (period + 1)
        values = self._price_history[-period:]

        if not values:
            return None

        ema = values[0]
        for price in values[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def _calculate_atr(self, period: int) -> Optional[float]:
        """Calculate Average True Range"""
        if len(self._price_history) < period + 1:
            return None

        true_ranges = []
        for i in range(-period, 0):
            high = max(self._price_history[i], self._price_history[i-1])
            low = min(self._price_history[i], self._price_history[i-1])
            true_range = high - low
            true_ranges.append(true_range)

        return sum(true_ranges) / len(true_ranges)

    def _calculate_stochastic(self, k_period: int, d_period: int) -> Optional[Dict[str, float]]:
        """Calculate Stochastic Oscillator"""
        if len(self._price_history) < k_period + d_period:
            return None

        high = max(self._price_history[-k_period:])
        low = min(self._price_history[-k_period:])
        current = self._price_history[-1]

        if high == low:
            k = 50.0
        else:
            k = ((current - low) / (high - low)) * 100

        # Calculate D (SMA of K)
        k_values = []
        for i in range(-d_period, 0):
            h = max(self._price_history[i-k_period:i])
            l = min(self._price_history[i-k_period:i])
            c = self._price_history[i-1]
            if h == l:
                k_values.append(50.0)
            else:
                k_values.append(((c - l) / (h - l)) * 100)

        d = sum(k_values) / len(k_values) if k_values else 50.0

        return {'k': k, 'd': d}

    def _calculate_williams(self, period: int) -> Optional[float]:
        """Calculate Williams %R"""
        if len(self._price_history) < period:
            return None

        high = max(self._price_history[-period:])
        low = min(self._price_history[-period:])
        current = self._price_history[-1]

        if high == low:
            return -50.0

        return -((high - current) / (high - low)) * 100

    def _calculate_cci(self, period: int) -> Optional[float]:
        """Calculate Commodity Channel Index"""
        if len(self._price_history) < period:
            return None

        typical_prices = []
        for i in range(-period, 0):
            high = max(self._price_history[i-1:i+1])
            low = min(self._price_history[i-1:i+1])
            typical = (high + low + self._price_history[i]) / 3
            typical_prices.append(typical)

        mean = sum(typical_prices) / len(typical_prices)
        mad = sum(abs(tp - mean) for tp in typical_prices) / len(typical_prices)

        if mad == 0:
            return 0

        return (typical_prices[-1] - mean) / (0.015 * mad)

    def _calculate_adx(self, period: int) -> Optional[float]:
        """Calculate Average Directional Index"""
        if len(self._price_history) < period + 1:
            return None

        # Simplified ADX calculation
        return 25.0  # Placeholder

    def _calculate_obv(self) -> Optional[float]:
        """Calculate On-Balance Volume"""
        if len(self._price_history) < 2 or len(self._volume_history) < 2:
            return None

        obv = 0
        for i in range(1, min(len(self._price_history), len(self._volume_history))):
            if self._price_history[-i] > self._price_history[-i-1]:
                obv += self._volume_history[-i]
            elif self._price_history[-i] < self._price_history[-i-1]:
                obv -= self._volume_history[-i]

        return obv

    async def _update_market_data(self):
        """Update market data from broker"""
        if not self._broker:
            return

        try:
            # Get ticker data
            ticker = await self._broker.get_ticker(self.config.symbol)
            if ticker:
                self._current_price = ticker.get('last') or ticker.get('price')

                # Update volume
                if 'volume' in ticker:
                    self._volume_history.append(ticker['volume'])
                    if len(self._volume_history) > self._max_history_length:
                        self._volume_history.pop(0)

        except Exception as e:
            logger.error(f"Error updating market data: {e}")

    async def _trigger_action(self):
        """Trigger the action when conditions are met"""
        async with self._state_lock:
            if self._triggered or self._state == ConditionalState.COOLDOWN:
                return

            self._triggered = True
            self._state = ConditionalState.TRIGGERED

            # Execute action
            try:
                success = await self._execute_action(self.config.action_on_true)

                if success:
                    self._executed = True
                    self._state = ConditionalState.EXECUTED
                    self.config.execution_count += 1
                    self._metrics.executions += 1
                    self._metrics.successful_executions += 1
                    self._last_execution_time = datetime.utcnow()

                    logger.info(f"Conditional order {self.config.name} executed successfully")

                    # Check if completed
                    if self.config.execution_count >= self.config.max_executions:
                        self._state = ConditionalState.COMPLETED
                        self._running = False

                    # Start cooldown
                    elif self.config.cooldown_period:
                        self._state = ConditionalState.COOLDOWN

                    # Execute false action if configured
                    if self.config.action_on_false:
                        await self._execute_action(self.config.action_on_false)

                else:
                    self._metrics.failed_executions += 1
                    logger.error(f"Failed to execute action for {self.config.name}")

            except Exception as e:
                self._metrics.failed_executions += 1
                logger.error(f"Error executing action: {e}")

            finally:
                # Reset triggered state for next check
                self._triggered = False

    async def _execute_action(self, action: ConditionalAction) -> bool:
        """Execute a conditional action"""
        try:
            if action.action_type == ConditionalActionType.PLACE_ORDER:
                return await self._execute_place_order(action)

            elif action.action_type == ConditionalActionType.CANCEL_ORDER:
                return await self._execute_cancel_order(action)

            elif action.action_type == ConditionalActionType.MODIFY_ORDER:
                return await self._execute_modify_order(action)

            elif action.action_type == ConditionalActionType.CLOSE_POSITION:
                return await self._execute_close_position(action)

            elif action.action_type == ConditionalActionType.SEND_ALERT:
                return await self._execute_send_alert(action)

            elif action.action_type == ConditionalActionType.EXECUTE_SCRIPT:
                return await self._execute_script(action)

            elif action.action_type == ConditionalActionType.WEBHOOK:
                return await self._execute_webhook(action)

            elif action.action_type == ConditionalActionType.NOTIFY:
                return await self._execute_notify(action)

            else:
                logger.warning(f"Unknown action type: {action.action_type}")
                return False

        except Exception as e:
            logger.error(f"Error executing action {action.action_type}: {e}")
            return False

    async def _execute_place_order(self, action: ConditionalAction) -> bool:
        """Execute place order action"""
        if not self._broker:
            return False

        try:
            order_params = {
                'symbol': action.symbol or self.config.symbol,
                'side': action.side or self.config.side,
                'order_type': action.order_type or self.config.order_type,
                'quantity': action.size or self.config.order_size,
                'time_in_force': action.time_in_force
            }

            if action.price:
                order_params['price'] = action.price
            elif self.config.order_price:
                order_params['price'] = self.config.order_price

            if action.stop_price:
                order_params['stop_price'] = action.stop_price
            elif self.config.order_stop_price:
                order_params['stop_price'] = self.config.order_stop_price

            result = await self._broker.place_order(**order_params)
            logger.info(f"Place order executed: {result.get('order_id')}")
            return True

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return False

    async def _execute_cancel_order(self, action: ConditionalAction) -> bool:
        """Execute cancel order action"""
        if not self._broker or not action.order_id:
            return False

        try:
            await self._broker.cancel_order(action.order_id)
            logger.info(f"Order {action.order_id} cancelled")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False

    async def _execute_modify_order(self, action: ConditionalAction) -> bool:
        """Execute modify order action"""
        if not self._broker or not action.order_id:
            return False

        try:
            modify_params = {}
            if action.price:
                modify_params['price'] = action.price
            if action.stop_price:
                modify_params['stop_price'] = action.stop_price
            if action.size:
                modify_params['quantity'] = action.size

            await self._broker.update_order(action.order_id, **modify_params)
            logger.info(f"Order {action.order_id} modified")
            return True

        except Exception as e:
            logger.error(f"Failed to modify order: {e}")
            return False

    async def _execute_close_position(self, action: ConditionalAction) -> bool:
        """Execute close position action"""
        if not self._broker:
            return False

        try:
            symbol = action.symbol or self.config.symbol
            await self._broker.close_position(symbol)
            logger.info(f"Position {symbol} closed")
            return True

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return False

    async def _execute_send_alert(self, action: ConditionalAction) -> bool:
        """Execute send alert action"""
        try:
            message = action.alert_message or f"Condition triggered for {self.config.name}"
            level = action.alert_level

            if level == "info":
                logger.info(f"ALERT: {message}")
            elif level == "warning":
                logger.warning(f"ALERT: {message}")
            elif level == "error":
                logger.error(f"ALERT: {message}")
            else:
                logger.info(f"ALERT: {message}")

            return True

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    async def _execute_script(self, action: ConditionalAction) -> bool:
        """Execute script action"""
        try:
            import subprocess
            result = subprocess.run(
                [action.script_path] + action.script_args,
                capture_output=True,
                text=True,
                timeout=30
            )
            logger.info(f"Script executed: {result.returncode}")
            return result.returncode == 0

        except Exception as e:
            logger.error(f"Failed to execute script: {e}")
            return False

    async def _execute_webhook(self, action: ConditionalAction) -> bool:
        """Execute webhook action"""
        if not action.webhook_url:
            return False

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = action.webhook_payload or {}
                async with session.post(action.webhook_url, json=payload) as response:
                    return response.status in [200, 201, 202]

        except Exception as e:
            logger.error(f"Failed to execute webhook: {e}")
            return False

    async def _execute_notify(self, action: ConditionalAction) -> bool:
        """Execute notification action"""
        try:
            message = action.notification_message or f"Condition triggered for {self.config.name}"
            channel = action.notification_channel or "default"

            # Here you would integrate with your notification system
            logger.info(f"NOTIFICATION [{channel}]: {message}")
            return True

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    async def _check_cooldown(self):
        """Check if cooldown period has elapsed"""
        if not self.config.cooldown_period or not self._last_execution_time:
            return

        elapsed = (datetime.utcnow() - self._last_execution_time).total_seconds()
        if elapsed >= self.config.cooldown_period:
            self._state = ConditionalState.ACTIVE
            logger.info(f"Cooldown complete for {self.config.name}")

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
        if 'volume' in data:
            self._volume_history.append(data['volume'])
            if len(self._volume_history) > self._max_history_length:
                self._volume_history.pop(0)

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
        """Convert conditional order to dictionary"""
        return {
            'id': self.id,
            'name': self.config.name,
            'state': self._state.value,
            'config': self.config.model_dump(),
            'metrics': self._metrics.model_dump(),
            'current_price': self._current_price,
            'triggered': self._triggered,
            'executed': self._executed,
            'consecutive_checks': self._consecutive_checks,
            'check_count': self._check_count,
            'last_execution_time': self._last_execution_time
        }

    @classmethod
    async def from_dict(
        cls,
        data: Dict[str, Any],
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ) -> 'ConditionalOrder':
        """Create conditional order from dictionary"""
        config = ConditionalOrderConfig(**data.get('config', {}))
        conditional_order = cls(config=config, broker=broker, order_manager=order_manager)

        # Restore state
        conditional_order._state = ConditionalState(data.get('state', 'pending'))
        conditional_order._current_price = data.get('current_price')
        conditional_order._triggered = data.get('triggered', False)
        conditional_order._executed = data.get('executed', False)
        conditional_order._consecutive_checks = data.get('consecutive_checks', 0)
        conditional_order._check_count = data.get('check_count', 0)

        if data.get('last_execution_time'):
            conditional_order._last_execution_time = data.get('last_execution_time')

        # Restore metrics
        if data.get('metrics'):
            conditional_order._metrics = ConditionalMetrics(**data.get('metrics'))

        # Restore price history
        if data.get('price_history'):
            conditional_order._price_history = data.get('price_history')

        if data.get('volume_history'):
            conditional_order._volume_history = data.get('volume_history')

        return conditional_order

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cancel()
        await self.stop_price_monitoring()
