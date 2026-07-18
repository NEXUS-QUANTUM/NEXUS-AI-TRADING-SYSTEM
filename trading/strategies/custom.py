# trading/strategies/custom.py
"""
NEXUS AI TRADING SYSTEM - Custom Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides a flexible custom strategy implementation that allows
users to define their own trading logic using a combination of:
- Technical indicators
- Price action patterns
- Custom conditions
- User-defined parameters

The strategy supports both simple and complex logic through a rule-based
system with condition-action pairs.
"""

import asyncio
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import deque

import numpy as np
import pandas as pd

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import MarketData, Signal, Position, Trade
from .base import BaseStrategy, StrategyConfig, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class ConditionOperator(str, Enum):
    """Operators for condition evaluation"""
    # Comparison operators
    EQUAL = "=="
    NOT_EQUAL = "!="
    GREATER = ">"
    GREATER_EQUAL = ">="
    LESS = "<"
    LESS_EQUAL = "<="
    
    # Logical operators
    AND = "and"
    OR = "or"
    NOT = "not"
    
    # Range operators
    BETWEEN = "between"
    NOT_BETWEEN = "not_between"
    
    # Crossover operators
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"
    
    # Threshold operators
    WITHIN = "within"
    OUTSIDE = "outside"


class ConditionType(str, Enum):
    """Types of conditions"""
    INDICATOR = "indicator"
    PRICE = "price"
    VOLUME = "volume"
    TIME = "time"
    POSITION = "position"
    PORTFOLIO = "portfolio"
    CUSTOM = "custom"


class ActionType(str, Enum):
    """Types of actions"""
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
    CLOSE_ALL = "close_all"
    SET_STOP_LOSS = "set_stop_loss"
    SET_TAKE_PROFIT = "set_take_profit"
    SET_TRAILING_STOP = "set_trailing_stop"
    ADJUST_POSITION = "adjust_position"
    SEND_ALERT = "send_alert"
    LOG_MESSAGE = "log_message"
    CUSTOM = "custom"


@dataclass
class IndicatorConfig:
    """Configuration for a technical indicator"""
    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    source: str = "close"  # close, high, low, open, volume
    period: Optional[int] = None
    column: Optional[str] = None


@dataclass
class Condition:
    """A condition for strategy logic"""
    condition_type: ConditionType
    operator: ConditionOperator
    left_value: Union[str, float, IndicatorConfig]
    right_value: Optional[Union[str, float, IndicatorConfig]] = None
    param1: Optional[float] = None
    param2: Optional[float] = None
    invert: bool = False
    custom_eval: Optional[Callable[[Dict[str, Any]], bool]] = None
    description: str = ""
    
    def __post_init__(self):
        if not self.description:
            self.description = self._generate_description()
    
    def _generate_description(self) -> str:
        """Generate a description of the condition."""
        if self.condition_type == ConditionType.CUSTOM:
            return "Custom condition"
        
        left = self._value_to_str(self.left_value)
        right = self._value_to_str(self.right_value)
        
        if self.operator == ConditionOperator.BETWEEN:
            return f"{left} between {self.param1 or 0} and {self.param2 or 0}"
        elif self.operator == ConditionOperator.CROSS_ABOVE:
            return f"{left} crosses above {right}"
        elif self.operator == ConditionOperator.CROSS_BELOW:
            return f"{left} crosses below {right}"
        else:
            invert_str = "NOT " if self.invert else ""
            return f"{invert_str}{left} {self.operator.value} {right}"
    
    def _value_to_str(self, value: Any) -> str:
        """Convert a value to string representation."""
        if isinstance(value, IndicatorConfig):
            return f"{value.name}({value.period or ''})"
        elif isinstance(value, (int, float)):
            return f"{value:.2f}"
        return str(value)


@dataclass
class Action:
    """An action to execute when conditions are met"""
    action_type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    condition: Optional[Condition] = None
    
    def __post_init__(self):
        if not self.description:
            self.description = self.action_type.value


@dataclass
class Rule:
    """A rule combining conditions and actions"""
    name: str
    conditions: List[Condition]
    actions: List[Action]
    priority: int = 0
    enabled: bool = True
    description: str = ""
    
    def __post_init__(self):
        if not self.description:
            self.description = f"Rule: {self.name}"
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate all conditions.
        
        Args:
            context: Evaluation context
            
        Returns:
            bool: True if all conditions are met
        """
        if not self.enabled:
            return False
        
        if not self.conditions:
            return True
        
        # Evaluate each condition
        for condition in self.conditions:
            if not self._evaluate_condition(condition, context):
                return False
        
        return True
    
    def _evaluate_condition(self, condition: Condition, context: Dict[str, Any]) -> bool:
        """Evaluate a single condition."""
        if condition.condition_type == ConditionType.CUSTOM:
            if condition.custom_eval:
                return condition.custom_eval(context)
            return False
        
        # Get left and right values
        left_value = self._get_value(condition.left_value, context)
        right_value = self._get_value(condition.right_value, context) if condition.right_value is not None else None
        
        # Evaluate based on operator
        result = self._evaluate_operator(condition.operator, left_value, right_value, condition.param1, condition.param2)
        
        if condition.invert:
            return not result
        return result
    
    def _get_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """Get the actual value from a value specification."""
        if isinstance(value, IndicatorConfig):
            return self._get_indicator_value(value, context)
        elif isinstance(value, str):
            return context.get(value, 0.0)
        else:
            return value
    
    def _get_indicator_value(self, indicator: IndicatorConfig, context: Dict[str, Any]) -> float:
        """Get indicator value from context."""
        # Build indicator key
        key = f"{indicator.name}"
        if indicator.period:
            key = f"{key}_{indicator.period}"
        if indicator.source:
            key = f"{key}_{indicator.source}"
        
        # Check if indicator value is in context
        if key in context:
            return context[key]
        
        # Check if indicators dictionary exists
        indicators = context.get("indicators", {})
        if indicator.name in indicators:
            return indicators[indicator.name].get(indicator.source or "value", 0.0)
        
        return 0.0
    
    def _evaluate_operator(
        self,
        operator: ConditionOperator,
        left: Any,
        right: Any,
        param1: Optional[float] = None,
        param2: Optional[float] = None,
    ) -> bool:
        """Evaluate the operator."""
        if operator == ConditionOperator.EQUAL:
            return left == right
        elif operator == ConditionOperator.NOT_EQUAL:
            return left != right
        elif operator == ConditionOperator.GREATER:
            return left > right
        elif operator == ConditionOperator.GREATER_EQUAL:
            return left >= right
        elif operator == ConditionOperator.LESS:
            return left < right
        elif operator == ConditionOperator.LESS_EQUAL:
            return left <= right
        elif operator == ConditionOperator.BETWEEN:
            return param1 is not None and param2 is not None and param1 <= left <= param2
        elif operator == ConditionOperator.NOT_BETWEEN:
            return param1 is not None and param2 is not None and not (param1 <= left <= param2)
        elif operator == ConditionOperator.WITHIN:
            return param1 is not None and abs(left - right) <= param1
        elif operator == ConditionOperator.OUTSIDE:
            return param1 is not None and abs(left - right) > param1
        elif operator == ConditionOperator.CROSS_ABOVE:
            return left > right and right is not None
        elif operator == ConditionOperator.CROSS_BELOW:
            return left < right and right is not None
        else:
            return False


@dataclass
class CustomStrategyConfig:
    """Configuration for custom strategy"""
    # Data sources
    indicators: List[IndicatorConfig] = field(default_factory=list)
    rules: List[Rule] = field(default_factory=list)
    
    # Default parameters
    default_position_size: float = 1000.0
    default_stop_loss_pct: float = 0.02
    default_take_profit_pct: float = 0.04
    min_confidence: float = 0.5
    
    # Execution settings
    max_position_size: float = 100000.0
    min_position_size: float = 10.0
    max_positions: int = 5
    cooldown_seconds: int = 0
    
    # Logging
    log_signals: bool = True
    log_actions: bool = True


# ============================================================================
# CUSTOM STRATEGY
# ============================================================================

class CustomStrategy(BaseStrategy):
    """
    Custom strategy implementation with rule-based logic.
    
    Users can define their own trading logic by specifying:
    - Technical indicators to calculate
    - Rules with conditions and actions
    - Position sizing and risk parameters
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        custom_config: Optional[CustomStrategyConfig] = None,
    ):
        """
        Initialize the custom strategy.
        
        Args:
            config: Strategy configuration
            custom_config: Custom strategy configuration
        """
        super().__init__(config)
        self.custom_config = custom_config or CustomStrategyConfig()
        
        # Data storage
        self._market_data: deque = deque(maxlen=500)
        self._indicator_values: Dict[str, Any] = {}
        self._indicator_history: Dict[str, deque] = {}
        
        # Context for rule evaluation
        self._context: Dict[str, Any] = {}
        
        # Action tracking
        self._action_history: List[Dict[str, Any]] = []
        self._last_action_time: Optional[datetime] = None
        
        self.logger = logger
    
    # ========================================================================
    # INDICATOR CALCULATIONS
    # ========================================================================
    
    def calculate_indicator(self, indicator: IndicatorConfig, data: pd.DataFrame) -> float:
        """
        Calculate an indicator value.
        
        Args:
            indicator: Indicator configuration
            data: Market data DataFrame
            
        Returns:
            float: Indicator value
        """
        if indicator.name.lower() == "sma":
            return self._calculate_sma(data, indicator)
        elif indicator.name.lower() == "ema":
            return self._calculate_ema(data, indicator)
        elif indicator.name.lower() == "rsi":
            return self._calculate_rsi(data, indicator)
        elif indicator.name.lower() == "macd":
            return self._calculate_macd(data, indicator)
        elif indicator.name.lower() == "bb":
            return self._calculate_bollinger_bands(data, indicator)
        elif indicator.name.lower() == "atr":
            return self._calculate_atr(data, indicator)
        elif indicator.name.lower() == "volume":
            return self._calculate_volume_indicator(data, indicator)
        elif indicator.name.lower() == "momentum":
            return self._calculate_momentum(data, indicator)
        elif indicator.name.lower() == "roc":
            return self._calculate_roc(data, indicator)
        elif indicator.name.lower() == "stoch":
            return self._calculate_stochastic(data, indicator)
        elif indicator.name.lower() == "adx":
            return self._calculate_adx(data, indicator)
        elif indicator.name.lower() == "cci":
            return self._calculate_cci(data, indicator)
        elif indicator.name.lower() == "williams":
            return self._calculate_williams_r(data, indicator)
        elif indicator.name.lower() == "obv":
            return self._calculate_obv(data, indicator)
        else:
            self.logger.warning(f"Unknown indicator: {indicator.name}")
            return 0.0
    
    def _calculate_sma(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Simple Moving Average."""
        period = indicator.period or 14
        source = indicator.source or "close"
        if len(data) < period:
            return 0.0
        return float(data[source].tail(period).mean())
    
    def _calculate_ema(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Exponential Moving Average."""
        period = indicator.period or 14
        source = indicator.source or "close"
        if len(data) < period:
            return 0.0
        return float(data[source].ewm(span=period, adjust=False).mean().iloc[-1])
    
    def _calculate_rsi(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Relative Strength Index."""
        period = indicator.period or 14
        source = indicator.source or "close"
        if len(data) < period + 1:
            return 50.0
        
        delta = data[source].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        if loss.iloc[-1] == 0:
            return 100.0
        
        rs = gain.iloc[-1] / loss.iloc[-1]
        return 100.0 - (100.0 / (1.0 + rs))
    
    def _calculate_macd(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate MACD."""
        source = indicator.source or "close"
        if len(data) < 26:
            return 0.0
        
        exp1 = data[source].ewm(span=12, adjust=False).mean()
        exp2 = data[source].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        
        return float(macd.iloc[-1])
    
    def _calculate_bollinger_bands(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Bollinger Bands (returns width)."""
        period = indicator.period or 20
        source = indicator.source or "close"
        if len(data) < period:
            return 0.0
        
        sma = data[source].rolling(window=period).mean()
        std = data[source].rolling(window=period).std()
        
        upper = sma + 2 * std
        lower = sma - 2 * std
        
        return float(((upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1] * 100) if sma.iloc[-1] != 0 else 0)
    
    def _calculate_atr(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Average True Range."""
        period = indicator.period or 14
        if len(data) < period + 1:
            return 0.0
        
        high = data['high']
        low = data['low']
        close = data['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return float(atr.iloc[-1])
    
    def _calculate_volume_indicator(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate volume indicator."""
        if 'volume' not in data.columns:
            return 0.0
        
        period = indicator.period or 20
        if len(data) < period:
            return 0.0
        
        avg_volume = data['volume'].tail(period).mean()
        current_volume = data['volume'].iloc[-1]
        
        return float(current_volume / avg_volume if avg_volume != 0 else 0)
    
    def _calculate_momentum(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate momentum."""
        period = indicator.period or 10
        source = indicator.source or "close"
        if len(data) < period + 1:
            return 0.0
        
        return float(data[source].iloc[-1] - data[source].iloc[-period - 1])
    
    def _calculate_roc(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Rate of Change."""
        period = indicator.period or 10
        source = indicator.source or "close"
        if len(data) < period + 1:
            return 0.0
        
        previous = data[source].iloc[-period - 1]
        current = data[source].iloc[-1]
        
        return float(((current - previous) / previous * 100) if previous != 0 else 0)
    
    def _calculate_stochastic(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Stochastic Oscillator."""
        period = indicator.period or 14
        if len(data) < period:
            return 50.0
        
        high = data['high'].tail(period)
        low = data['low'].tail(period)
        
        highest_high = high.max()
        lowest_low = low.min()
        
        current_close = data['close'].iloc[-1]
        
        if highest_high == lowest_low:
            return 50.0
        
        return float((current_close - lowest_low) / (highest_high - lowest_low) * 100)
    
    def _calculate_adx(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Average Directional Index."""
        period = indicator.period or 14
        if len(data) < period * 2:
            return 25.0
        
        # Simplified ADX calculation
        high = data['high']
        low = data['low']
        
        tr = pd.concat([
            high - low,
            abs(high - high.shift()),
            abs(low - low.shift())
        ], axis=1).max(axis=1)
        
        return float(tr.rolling(window=period).mean().iloc[-1] / data['close'].mean() * 100)
    
    def _calculate_cci(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Commodity Channel Index."""
        period = indicator.period or 20
        if len(data) < period:
            return 0.0
        
        tp = (data['high'] + data['low'] + data['close']) / 3
        sma_tp = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: abs(x - x.mean()).mean())
        
        if mad.iloc[-1] == 0:
            return 0.0
        
        return float((tp.iloc[-1] - sma_tp.iloc[-1]) / (0.015 * mad.iloc[-1]))
    
    def _calculate_williams_r(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate Williams %R."""
        period = indicator.period or 14
        if len(data) < period:
            return -50.0
        
        highest_high = data['high'].tail(period).max()
        lowest_low = data['low'].tail(period).min()
        current_close = data['close'].iloc[-1]
        
        if highest_high == lowest_low:
            return -50.0
        
        return float((highest_high - current_close) / (highest_high - lowest_low) * -100)
    
    def _calculate_obv(self, data: pd.DataFrame, indicator: IndicatorConfig) -> float:
        """Calculate On-Balance Volume."""
        if 'volume' not in data.columns:
            return 0.0
        
        # Simplified OBV
        obv = 0
        for i in range(1, len(data)):
            if data['close'].iloc[i] > data['close'].iloc[i-1]:
                obv += data['volume'].iloc[i]
            elif data['close'].iloc[i] < data['close'].iloc[i-1]:
                obv -= data['volume'].iloc[i]
        
        return float(obv)
    
    # ========================================================================
    # CONTEXT BUILDING
    # ========================================================================
    
    def _build_context(
        self,
        market_data: List[MarketData],
    ) -> Dict[str, Any]:
        """
        Build evaluation context from market data.
        
        Args:
            market_data: Market data
            
        Returns:
            Dict[str, Any]: Evaluation context
        """
        if not market_data:
            return {}
        
        # Get latest data
        latest = market_data[-1]
        
        # Build DataFrame for indicators
        df = pd.DataFrame([
            {
                'open': c.open,
                'high': c.high,
                'low': c.low,
                'close': c.close,
                'volume': c.volume or 0,
                'timestamp': c.timestamp,
            }
            for c in market_data
        ])
        
        context = {
            'symbol': latest.symbol,
            'price': latest.close,
            'open': latest.open,
            'high': latest.high,
            'low': latest.low,
            'volume': latest.volume or 0,
            'market_data': market_data,
            'dataframe': df,
            'positions': {p.symbol: p for p in self.positions.values()},
            'metrics': self.metrics,
            'indicators': {},
        }
        
        # Calculate all indicators
        for indicator in self.custom_config.indicators:
            value = self.calculate_indicator(indicator, df)
            key = f"{indicator.name}_{indicator.period or ''}_{indicator.source or 'value'}"
            context['indicators'][key] = value
            context[key] = value
            
            # Store history
            if key not in self._indicator_history:
                self._indicator_history[key] = deque(maxlen=100)
            self._indicator_history[key].append(value)
        
        return context
    
    # ========================================================================
    # ACTION EXECUTION
    # ========================================================================
    
    async def execute_action(
        self,
        action: Action,
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Execute an action and generate a signal.
        
        Args:
            action: Action to execute
            context: Execution context
            
        Returns:
            Optional[Signal]: Generated signal
        """
        symbol = context.get('symbol', self.config.symbol or '')
        price = context.get('price', 0.0)
        
        if action.action_type == ActionType.BUY:
            return await self._execute_buy(action, symbol, price, context)
        
        elif action.action_type == ActionType.SELL:
            return await self._execute_sell(action, symbol, price, context)
        
        elif action.action_type == ActionType.CLOSE:
            return await self._execute_close(action, symbol, context)
        
        elif action.action_type == ActionType.CLOSE_ALL:
            return await self._execute_close_all(action, context)
        
        elif action.action_type == ActionType.SET_STOP_LOSS:
            return await self._execute_set_stop_loss(action, symbol, price, context)
        
        elif action.action_type == ActionType.SET_TAKE_PROFIT:
            return await self._execute_set_take_profit(action, symbol, price, context)
        
        elif action.action_type == ActionType.SET_TRAILING_STOP:
            return await self._execute_set_trailing_stop(action, symbol, price, context)
        
        elif action.action_type == ActionType.SEND_ALERT:
            await self._execute_send_alert(action, context)
            return None
        
        elif action.action_type == ActionType.LOG_MESSAGE:
            self._execute_log_message(action, context)
            return None
        
        else:
            self.logger.warning(f"Unknown action type: {action.action_type}")
            return None
    
    async def _execute_buy(
        self,
        action: Action,
        symbol: str,
        price: float,
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Execute a buy action."""
        position_size = action.params.get('size', self.custom_config.default_position_size)
        stop_loss_pct = action.params.get('stop_loss_pct', self.custom_config.default_stop_loss_pct)
        take_profit_pct = action.params.get('take_profit_pct', self.custom_config.default_take_profit_pct)
        
        stop_loss = price * (1 - stop_loss_pct) if stop_loss_pct > 0 else None
        take_profit = price * (1 + take_profit_pct) if take_profit_pct > 0 else None
        
        return Signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            strength=SignalStrength.MEDIUM,
            confidence=self.custom_config.min_confidence,
            price=price,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.utcnow(),
            metadata={
                "action_type": action.action_type.value,
                "action_description": action.description,
                "reason": action.params.get('reason', ''),
            },
        )
    
    async def _execute_sell(
        self,
        action: Action,
        symbol: str,
        price: float,
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Execute a sell action."""
        position_size = action.params.get('size', self.custom_config.default_position_size)
        stop_loss_pct = action.params.get('stop_loss_pct', self.custom_config.default_stop_loss_pct)
        take_profit_pct = action.params.get('take_profit_pct', self.custom_config.default_take_profit_pct)
        
        stop_loss = price * (1 + stop_loss_pct) if stop_loss_pct > 0 else None
        take_profit = price * (1 - take_profit_pct) if take_profit_pct > 0 else None
        
        return Signal(
            symbol=symbol,
            signal_type=SignalType.SELL,
            strength=SignalStrength.MEDIUM,
            confidence=self.custom_config.min_confidence,
            price=price,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.utcnow(),
            metadata={
                "action_type": action.action_type.value,
                "action_description": action.description,
                "reason": action.params.get('reason', ''),
            },
        )
    
    async def _execute_close(
        self,
        action: Action,
        symbol: str,
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Execute a close action."""
        if symbol not in self.positions:
            return None
        
        return Signal(
            symbol=symbol,
            signal_type=SignalType.CLOSE,
            strength=SignalStrength.MEDIUM,
            confidence=self.custom_config.min_confidence,
            price=context.get('price', 0.0),
            timestamp=datetime.utcnow(),
            metadata={
                "action_type": action.action_type.value,
                "action_description": action.description,
                "reason": action.params.get('reason', ''),
            },
        )
    
    async def _execute_close_all(
        self,
        action: Action,
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Execute a close all action."""
        # Close all positions by sending close signals for each
        for symbol in list(self.positions.keys()):
            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                strength=SignalStrength.STRONG,
                confidence=1.0,
                price=context.get('price', 0.0),
                timestamp=datetime.utcnow(),
                metadata={
                    "action_type": action.action_type.value,
                    "action_description": action.description,
                    "reason": action.params.get('reason', 'Closing all positions'),
                },
            )
            # Process signal
            await self.process_signal(signal)
        
        return None
    
    async def _execute_set_stop_loss(
        self,
        action: Action,
        symbol: str,
        price: float,
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Execute a set stop loss action."""
        stop_loss_pct = action.params.get('stop_loss_pct', self.custom_config.default_stop_loss_pct)
        stop_loss = price * (1 - stop_loss_pct) if stop_loss_pct > 0 else None
        
        if symbol in self.positions:
            position = self.positions[symbol]
            position.stop_loss = stop_loss
            await self.update_position(position)
        
        return None
    
    async def _execute_set_take_profit(
        self,
        action: Action,
        symbol: str,
        price: float,
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Execute a set take profit action."""
        take_profit_pct = action.params.get('take_profit_pct', self.custom_config.default_take_profit_pct)
        take_profit = price * (1 + take_profit_pct) if take_profit_pct > 0 else None
        
        if symbol in self.positions:
            position = self.positions[symbol]
            position.take_profit = take_profit
            await self.update_position(position)
        
        return None
    
    async def _execute_set_trailing_stop(
        self,
        action: Action,
        symbol: str,
        price: float,
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Execute a set trailing stop action."""
        trailing_pct = action.params.get('trailing_pct', 0.02)
        
        if symbol in self.positions:
            position = self.positions[symbol]
            position.trailing_stop_pct = trailing_pct
            await self.update_position(position)
        
        return None
    
    async def _execute_send_alert(
        self,
        action: Action,
        context: Dict[str, Any],
    ) -> None:
        """Execute a send alert action."""
        message = action.params.get('message', 'Alert triggered')
        self.logger.info(f"ALERT: {message}")
        # In practice, this would send to notification service
    
    def _execute_log_message(
        self,
        action: Action,
        context: Dict[str, Any],
    ) -> None:
        """Execute a log message action."""
        message = action.params.get('message', 'Log entry')
        self.logger.info(f"LOG: {message}")
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signal(
        self,
        market_data: List[MarketData],
    ) -> Optional[Signal]:
        """
        Generate a trading signal based on custom rules.
        
        Args:
            market_data: Market data
            
        Returns:
            Optional[Signal]: Trading signal
        """
        if not market_data:
            return None
        
        # Update market data
        self._market_data.extend(market_data)
        
        # Build context
        context = self._build_context(market_data)
        self._context = context
        
        # Check cooldown
        if self._last_action_time and self.custom_config.cooldown_seconds > 0:
            elapsed = (datetime.utcnow() - self._last_action_time).total_seconds()
            if elapsed < self.custom_config.cooldown_seconds:
                return None
        
        # Evaluate rules
        signals = []
        
        for rule in self.custom_config.rules:
            if not rule.enabled:
                continue
            
            try:
                if rule.evaluate(context):
                    # Rule conditions are met, execute actions
                    for action in rule.actions:
                        signal = await self.execute_action(action, context)
                        if signal:
                            signals.append(signal)
                            
                            # Track action
                            self._action_history.append({
                                "rule": rule.name,
                                "action": action.action_type.value,
                                "description": action.description,
                                "timestamp": datetime.utcnow().isoformat(),
                            })
                            
                            # Update last action time
                            self._last_action_time = datetime.utcnow()
                            
                            if self.custom_config.log_actions:
                                self.logger.info(f"Executed action: {action.description}")
            
            except Exception as e:
                self.logger.error(f"Error evaluating rule {rule.name}: {e}")
                continue
        
        # Return the first signal (or most important)
        if signals:
            return signals[0]
        
        return None
    
    # ========================================================================
    # STRATEGY MANAGEMENT
    # ========================================================================
    
    def add_rule(self, rule: Rule) -> None:
        """
        Add a new rule to the strategy.
        
        Args:
            rule: Rule to add
        """
        self.custom_config.rules.append(rule)
        self.logger.info(f"Added rule: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a rule by name.
        
        Args:
            rule_name: Name of rule to remove
            
        Returns:
            bool: True if rule was removed
        """
        for i, rule in enumerate(self.custom_config.rules):
            if rule.name == rule_name:
                self.custom_config.rules.pop(i)
                self.logger.info(f"Removed rule: {rule_name}")
                return True
        return False
    
    def enable_rule(self, rule_name: str) -> bool:
        """
        Enable a rule by name.
        
        Args:
            rule_name: Name of rule to enable
            
        Returns:
            bool: True if rule was enabled
        """
        for rule in self.custom_config.rules:
            if rule.name == rule_name:
                rule.enabled = True
                self.logger.info(f"Enabled rule: {rule_name}")
                return True
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        """
        Disable a rule by name.
        
        Args:
            rule_name: Name of rule to disable
            
        Returns:
            bool: True if rule was disabled
        """
        for rule in self.custom_config.rules:
            if rule.name == rule_name:
                rule.enabled = False
                self.logger.info(f"Disabled rule: {rule_name}")
                return True
        return False
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """
        Get all rules as dictionaries.
        
        Returns:
            List[Dict[str, Any]]: Rules
        """
        return [
            {
                "name": rule.name,
                "enabled": rule.enabled,
                "priority": rule.priority,
                "description": rule.description,
                "conditions": [
                    {
                        "type": c.condition_type.value,
                        "operator": c.operator.value,
                        "description": c.description,
                    }
                    for c in rule.conditions
                ],
                "actions": [
                    {
                        "type": a.action_type.value,
                        "description": a.description,
                    }
                    for a in rule.actions
                ],
            }
            for rule in self.custom_config.rules
        ]
    
    # ========================================================================
    # EXPORT/IMPORT
    # ========================================================================
    
    def export_config(self) -> Dict[str, Any]:
        """
        Export strategy configuration.
        
        Returns:
            Dict[str, Any]: Strategy configuration
        """
        return {
            "name": self.config.name,
            "strategy_type": self.config.strategy_type.value,
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "custom_config": {
                "indicators": [
                    {
                        "name": ind.name,
                        "params": ind.params,
                        "source": ind.source,
                        "period": ind.period,
                    }
                    for ind in self.custom_config.indicators
                ],
                "rules": [
                    {
                        "name": rule.name,
                        "conditions": [
                            {
                                "type": c.condition_type.value,
                                "operator": c.operator.value,
                                "left_value": c.left_value,
                                "right_value": c.right_value,
                                "param1": c.param1,
                                "param2": c.param2,
                                "invert": c.invert,
                                "description": c.description,
                            }
                            for c in rule.conditions
                        ],
                        "actions": [
                            {
                                "type": a.action_type.value,
                                "params": a.params,
                                "description": a.description,
                            }
                            for a in rule.actions
                        ],
                        "enabled": rule.enabled,
                        "priority": rule.priority,
                        "description": rule.description,
                    }
                    for rule in self.custom_config.rules
                ],
                "default_position_size": self.custom_config.default_position_size,
                "default_stop_loss_pct": self.custom_config.default_stop_loss_pct,
                "default_take_profit_pct": self.custom_config.default_take_profit_pct,
                "min_confidence": self.custom_config.min_confidence,
                "max_positions": self.custom_config.max_positions,
                "cooldown_seconds": self.custom_config.cooldown_seconds,
            },
        }
    
    @classmethod
    def from_config(
        cls,
        config: StrategyConfig,
        custom_config: Union[Dict[str, Any], CustomStrategyConfig],
    ) -> "CustomStrategy":
        """
        Create a custom strategy from configuration.
        
        Args:
            config: Strategy configuration
            custom_config: Custom configuration dictionary or object
            
        Returns:
            CustomStrategy: Custom strategy instance
        """
        if isinstance(custom_config, dict):
            custom_config = cls._dict_to_custom_config(custom_config)
        
        return cls(config, custom_config)
    
    @classmethod
    def _dict_to_custom_config(cls, data: Dict[str, Any]) -> CustomStrategyConfig:
        """Convert dictionary to CustomStrategyConfig."""
        config = CustomStrategyConfig()
        
        # Indicators
        if "indicators" in data:
            for ind_data in data["indicators"]:
                config.indicators.append(IndicatorConfig(**ind_data))
        
        # Rules
        if "rules" in data:
            for rule_data in data["rules"]:
                conditions = []
                for cond_data in rule_data.get("conditions", []):
                    conditions.append(Condition(**cond_data))
                
                actions = []
                for act_data in rule_data.get("actions", []):
                    actions.append(Action(**act_data))
                
                config.rules.append(Rule(
                    name=rule_data.get("name", "Rule"),
                    conditions=conditions,
                    actions=actions,
                    enabled=rule_data.get("enabled", True),
                    priority=rule_data.get("priority", 0),
                    description=rule_data.get("description", ""),
                ))
        
        # Other parameters
        config.default_position_size = data.get("default_position_size", config.default_position_size)
        config.default_stop_loss_pct = data.get("default_stop_loss_pct", config.default_stop_loss_pct)
        config.default_take_profit_pct = data.get("default_take_profit_pct", config.default_take_profit_pct)
        config.min_confidence = data.get("min_confidence", config.min_confidence)
        config.max_positions = data.get("max_positions", config.max_positions)
        config.cooldown_seconds = data.get("cooldown_seconds", config.cooldown_seconds)
        
        return config
    
    # ========================================================================
    # LIFECYCLE
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        await super().on_start()
        self.logger.info(f"Custom strategy started with {len(self.custom_config.rules)} rules")
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        await super().on_stop()
        self.logger.info("Custom strategy stopped")
    
    def get_custom_stats(self) -> Dict[str, Any]:
        """
        Get custom strategy statistics.
        
        Returns:
            Dict[str, Any]: Strategy statistics
        """
        return {
            "rules": len(self.custom_config.rules),
            "enabled_rules": sum(1 for r in self.custom_config.rules if r.enabled),
            "indicators": len(self.custom_config.indicators),
            "actions_performed": len(self._action_history),
            "last_action": self._action_history[-1] if self._action_history else None,
        }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ConditionOperator",
    "ConditionType",
    "ActionType",
    "IndicatorConfig",
    "Condition",
    "Action",
    "Rule",
    "CustomStrategyConfig",
    "CustomStrategy",
]
