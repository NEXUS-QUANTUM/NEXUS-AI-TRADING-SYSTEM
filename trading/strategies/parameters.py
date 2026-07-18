# trading/strategies/parameters.py
"""
NEXUS AI TRADING SYSTEM - Strategy Parameters
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides parameter management for trading strategies,
including parameter validation, optimization, and persistence.
It supports both static and dynamic parameter configurations
with versioning and validation.

Key Features:
- Parameter validation with schemas
- Parameter optimization (grid search, Bayesian)
- Parameter persistence and versioning
- Dynamic parameter updates
- Sensitivity analysis
- Parameter constraints and dependencies
"""

import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import defaultdict, deque

import numpy as np
from pydantic import BaseModel, Field, validator, root_validator

from shared.utilities.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class ParameterType(str, Enum):
    """Types of strategy parameters"""
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    CHOICE = "choice"
    MULTI_CHOICE = "multi_choice"
    RANGE = "range"
    PERCENTAGE = "percentage"
    TIMEFRAME = "timeframe"
    SYMBOL = "symbol"
    ORDER_TYPE = "order_type"
    CUSTOM = "custom"


class ParameterScope(str, Enum):
    """Scope of parameters"""
    GLOBAL = "global"          # Applied to all strategies
    STRATEGY = "strategy"      # Strategy-specific
    SYMBOL = "symbol"          # Symbol-specific
    TIMEFRAME = "timeframe"    # Timeframe-specific
    INSTANCE = "instance"      # Instance-specific


class ParameterConstraint(str, Enum):
    """Parameter constraints"""
    MIN = "min"
    MAX = "max"
    STEP = "step"
    CHOICES = "choices"
    DEPENDENCY = "dependency"
    MUTUAL_EXCLUSION = "mutual_exclusion"
    REQUIRED = "required"
    OPTIONAL = "optional"


@dataclass
class ParameterDefinition:
    """Definition of a parameter"""
    name: str
    param_type: ParameterType
    description: str = ""
    default: Any = None
    required: bool = False
    
    # Constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[Any]] = None
    
    # Dependencies
    depends_on: Optional[Dict[str, Any]] = None
    mutual_exclusion: Optional[List[str]] = None
    
    # Scope
    scope: ParameterScope = ParameterScope.STRATEGY
    
    # Validation
    validation_fn: Optional[Callable[[Any], bool]] = None
    transform_fn: Optional[Callable[[Any], Any]] = None
    
    # Metadata
    category: str = "general"
    display_name: str = ""
    order: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self, value: Any) -> bool:
        """
        Validate a parameter value.
        
        Args:
            value: Value to validate
            
        Returns:
            bool: True if valid
        """
        # Type validation
        if self.param_type == ParameterType.INTEGER:
            if not isinstance(value, int):
                return False
        elif self.param_type == ParameterType.FLOAT:
            if not isinstance(value, (int, float)):
                return False
        elif self.param_type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                return False
        elif self.param_type == ParameterType.STRING:
            if not isinstance(value, str):
                return False
        elif self.param_type == ParameterType.CHOICE:
            if value not in (self.choices or []):
                return False
        elif self.param_type == ParameterType.MULTI_CHOICE:
            if not isinstance(value, list):
                return False
            if not all(v in (self.choices or []) for v in value):
                return False
        
        # Range validation
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        
        # Step validation
        if self.step is not None and self.param_type in [ParameterType.INTEGER, ParameterType.FLOAT]:
            if isinstance(value, (int, float)):
                if abs(value % self.step) > 1e-9:
                    return False
        
        # Custom validation
        if self.validation_fn:
            return self.validation_fn(value)
        
        return True
    
    def transform(self, value: Any) -> Any:
        """
        Transform a parameter value.
        
        Args:
            value: Value to transform
            
        Returns:
            Any: Transformed value
        """
        if self.transform_fn:
            return self.transform_fn(value)
        
        if self.param_type == ParameterType.PERCENTAGE:
            if isinstance(value, (int, float)):
                return value / 100.0
        
        if self.param_type == ParameterType.TIMEFRAME:
            return str(value)
        
        return value
    
    def get_default(self) -> Any:
        """Get default value."""
        return self.default
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.param_type.value,
            "description": self.description,
            "default": self.default,
            "required": self.required,
            "min": self.min_value,
            "max": self.max_value,
            "step": self.step,
            "choices": self.choices,
            "depends_on": self.depends_on,
            "mutual_exclusion": self.mutual_exclusion,
            "scope": self.scope.value,
            "category": self.category,
            "display_name": self.display_name or self.name,
            "order": self.order,
            "metadata": self.metadata,
        }


@dataclass
class ParameterSet:
    """A complete set of parameters"""
    name: str
    version: str = "1.0.0"
    parameters: Dict[str, Any] = field(default_factory=dict)
    definitions: Dict[str, ParameterDefinition] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get(self, name: str, default: Any = None) -> Any:
        """Get a parameter value."""
        return self.parameters.get(name, default)
    
    def set(self, name: str, value: Any) -> bool:
        """
        Set a parameter value.
        
        Args:
            name: Parameter name
            value: Parameter value
            
        Returns:
            bool: True if set successfully
        """
        if name in self.definitions:
            if not self.definitions[name].validate(value):
                return False
            value = self.definitions[name].transform(value)
        
        self.parameters[name] = value
        self.updated_at = datetime.utcnow()
        return True
    
    def validate_all(self) -> List[str]:
        """
        Validate all parameters.
        
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        for name, definition in self.definitions.items():
            value = self.parameters.get(name, definition.default)
            
            if definition.required and value is None:
                errors.append(f"Required parameter '{name}' is missing")
                continue
            
            if value is not None:
                if not definition.validate(value):
                    errors.append(f"Invalid value for parameter '{name}': {value}")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "parameters": self.parameters,
            "definitions": {
                name: defn.to_dict() for name, defn in self.definitions.items()
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParameterSet":
        """Create from dictionary."""
        definitions = {}
        for name, defn_data in data.get("definitions", {}).items():
            definitions[name] = ParameterDefinition(**defn_data)
        
        return cls(
            name=data.get("name", "default"),
            version=data.get("version", "1.0.0"),
            parameters=data.get("parameters", {}),
            definitions=definitions,
            metadata=data.get("metadata", {}),
        )


# ============================================================================
# PARAMETER SCHEMAS
# ============================================================================

class StrategyParameterSchema:
    """
    Schema definition for strategy parameters.
    
    Provides pre-defined parameter schemas for common strategy types.
    """
    
    @staticmethod
    def get_schema(strategy_type: str) -> Dict[str, ParameterDefinition]:
        """
        Get parameter schema for a strategy type.
        
        Args:
            strategy_type: Type of strategy
            
        Returns:
            Dict[str, ParameterDefinition]: Parameter definitions
        """
        schemas = {
            "trend_following": StrategyParameterSchema._trend_following_schema(),
            "mean_reversion": StrategyParameterSchema._mean_reversion_schema(),
            "breakout": StrategyParameterSchema._breakout_schema(),
            "arbitrage": StrategyParameterSchema._arbitrage_schema(),
            "scalping": StrategyParameterSchema._scalping_schema(),
            "momentum": StrategyParameterSchema._momentum_schema(),
            "grid": StrategyParameterSchema._grid_schema(),
            "ai_ensemble": StrategyParameterSchema._ai_ensemble_schema(),
            "martingale": StrategyParameterSchema._martingale_schema(),
            "pairs": StrategyParameterSchema._pairs_schema(),
        }
        
        return schemas.get(strategy_type, {})
    
    @staticmethod
    def _trend_following_schema() -> Dict[str, ParameterDefinition]:
        """Trend following parameter schema."""
        return {
            "fast_ma_period": ParameterDefinition(
                name="fast_ma_period",
                param_type=ParameterType.INTEGER,
                description="Fast moving average period",
                default=10,
                min_value=2,
                max_value=50,
                category="indicators",
                display_name="Fast MA Period",
                order=1,
            ),
            "slow_ma_period": ParameterDefinition(
                name="slow_ma_period",
                param_type=ParameterType.INTEGER,
                description="Slow moving average period",
                default=50,
                min_value=10,
                max_value=200,
                category="indicators",
                display_name="Slow MA Period",
                order=2,
            ),
            "signal_ma_period": ParameterDefinition(
                name="signal_ma_period",
                param_type=ParameterType.INTEGER,
                description="Signal line period",
                default=9,
                min_value=2,
                max_value=30,
                category="indicators",
                display_name="Signal MA Period",
                order=3,
            ),
            "trend_strength_threshold": ParameterDefinition(
                name="trend_strength_threshold",
                param_type=ParameterType.PERCENTAGE,
                description="Minimum trend strength threshold",
                default=1.0,
                min_value=0.0,
                max_value=5.0,
                step=0.1,
                category="filters",
                display_name="Trend Strength Threshold",
                order=4,
            ),
            "use_adx_filter": ParameterDefinition(
                name="use_adx_filter",
                param_type=ParameterType.BOOLEAN,
                description="Use ADX trend filter",
                default=True,
                category="filters",
                display_name="Use ADX Filter",
                order=5,
            ),
            "adx_threshold": ParameterDefinition(
                name="adx_threshold",
                param_type=ParameterType.INTEGER,
                description="ADX threshold for trend strength",
                default=25,
                min_value=10,
                max_value=50,
                depends_on={"use_adx_filter": True},
                category="filters",
                display_name="ADX Threshold",
                order=6,
            ),
        }
    
    @staticmethod
    def _mean_reversion_schema() -> Dict[str, ParameterDefinition]:
        """Mean reversion parameter schema."""
        return {
            "bb_period": ParameterDefinition(
                name="bb_period",
                param_type=ParameterType.INTEGER,
                description="Bollinger Bands period",
                default=20,
                min_value=5,
                max_value=50,
                category="indicators",
                display_name="BB Period",
                order=1,
            ),
            "bb_std_dev": ParameterDefinition(
                name="bb_std_dev",
                param_type=ParameterType.FLOAT,
                description="Bollinger Bands standard deviation",
                default=2.0,
                min_value=1.0,
                max_value=3.5,
                step=0.1,
                category="indicators",
                display_name="BB Std Dev",
                order=2,
            ),
            "rsi_period": ParameterDefinition(
                name="rsi_period",
                param_type=ParameterType.INTEGER,
                description="RSI period",
                default=14,
                min_value=5,
                max_value=30,
                category="indicators",
                display_name="RSI Period",
                order=3,
            ),
            "rsi_oversold": ParameterDefinition(
                name="rsi_oversold",
                param_type=ParameterType.INTEGER,
                description="RSI oversold threshold",
                default=30,
                min_value=10,
                max_value=45,
                category="indicators",
                display_name="RSI Oversold",
                order=4,
            ),
            "rsi_overbought": ParameterDefinition(
                name="rsi_overbought",
                param_type=ParameterType.INTEGER,
                description="RSI overbought threshold",
                default=70,
                min_value=55,
                max_value=90,
                category="indicators",
                display_name="RSI Overbought",
                order=5,
            ),
            "entry_zscore": ParameterDefinition(
                name="entry_zscore",
                param_type=ParameterType.FLOAT,
                description="Entry Z-score threshold",
                default=2.0,
                min_value=0.5,
                max_value=4.0,
                step=0.1,
                category="entry",
                display_name="Entry Z-Score",
                order=6,
            ),
            "exit_zscore": ParameterDefinition(
                name="exit_zscore",
                param_type=ParameterType.FLOAT,
                description="Exit Z-score threshold",
                default=0.5,
                min_value=0.0,
                max_value=2.0,
                step=0.1,
                category="exit",
                display_name="Exit Z-Score",
                order=7,
            ),
        }
    
    @staticmethod
    def _breakout_schema() -> Dict[str, ParameterDefinition]:
        """Breakout parameter schema."""
        return {
            "breakout_period": ParameterDefinition(
                name="breakout_period",
                param_type=ParameterType.INTEGER,
                description="Breakout detection period",
                default=20,
                min_value=5,
                max_value=100,
                category="indicators",
                display_name="Breakout Period",
                order=1,
            ),
            "breakout_threshold": ParameterDefinition(
                name="breakout_threshold",
                param_type=ParameterType.PERCENTAGE,
                description="Breakout confirmation threshold",
                default=0.5,
                min_value=0.0,
                max_value=5.0,
                step=0.1,
                category="entry",
                display_name="Breakout Threshold",
                order=2,
            ),
            "volume_confirmation": ParameterDefinition(
                name="volume_confirmation",
                param_type=ParameterType.BOOLEAN,
                description="Require volume confirmation",
                default=True,
                category="filters",
                display_name="Volume Confirmation",
                order=3,
            ),
            "volume_ratio": ParameterDefinition(
                name="volume_ratio",
                param_type=ParameterType.FLOAT,
                description="Minimum volume ratio for confirmation",
                default=1.5,
                min_value=1.0,
                max_value=5.0,
                step=0.1,
                depends_on={"volume_confirmation": True},
                category="filters",
                display_name="Volume Ratio",
                order=4,
            ),
            "retest_confirmation": ParameterDefinition(
                name="retest_confirmation",
                param_type=ParameterType.BOOLEAN,
                description="Require retest confirmation",
                default=True,
                category="entry",
                display_name="Retest Confirmation",
                order=5,
            ),
            "false_breakout_filter": ParameterDefinition(
                name="false_breakout_filter",
                param_type=ParameterType.BOOLEAN,
                description="Filter false breakouts",
                default=True,
                category="filters",
                display_name="False Breakout Filter",
                order=6,
            ),
        }
    
    @staticmethod
    def _arbitrage_schema() -> Dict[str, ParameterDefinition]:
        """Arbitrage parameter schema."""
        return {
            "min_profit_percent": ParameterDefinition(
                name="min_profit_percent",
                param_type=ParameterType.PERCENTAGE,
                description="Minimum profit percentage",
                default=0.5,
                min_value=0.0,
                max_value=5.0,
                step=0.1,
                category="entry",
                display_name="Min Profit %",
                order=1,
            ),
            "max_position_size": ParameterDefinition(
                name="max_position_size",
                param_type=ParameterType.FLOAT,
                description="Maximum position size",
                default=10000.0,
                min_value=100.0,
                max_value=1000000.0,
                category="risk",
                display_name="Max Position Size",
                order=2,
            ),
            "max_risk_per_trade": ParameterDefinition(
                name="max_risk_per_trade",
                param_type=ParameterType.PERCENTAGE,
                description="Maximum risk per trade",
                default=1.0,
                min_value=0.0,
                max_value=5.0,
                step=0.1,
                category="risk",
                display_name="Max Risk %",
                order=3,
            ),
            "arbitrage_types": ParameterDefinition(
                name="arbitrage_types",
                param_type=ParameterType.MULTI_CHOICE,
                description="Types of arbitrage to use",
                default=["triangular", "statistical"],
                choices=["triangular", "statistical", "cross_exchange", "futures_spot"],
                category="strategy",
                display_name="Arbitrage Types",
                order=4,
            ),
            "max_slippage": ParameterDefinition(
                name="max_slippage",
                param_type=ParameterType.PERCENTAGE,
                description="Maximum allowed slippage",
                default=0.5,
                min_value=0.0,
                max_value=2.0,
                step=0.1,
                category="execution",
                display_name="Max Slippage",
                order=5,
            ),
        }
    
    @staticmethod
    def _scalping_schema() -> Dict[str, ParameterDefinition]:
        """Scalping parameter schema."""
        return {
            "entry_window": ParameterDefinition(
                name="entry_window",
                param_type=ParameterType.INTEGER,
                description="Entry window (bars)",
                default=5,
                min_value=1,
                max_value=20,
                category="entry",
                display_name="Entry Window",
                order=1,
            ),
            "target_profit": ParameterDefinition(
                name="target_profit",
                param_type=ParameterType.PERCENTAGE,
                description="Target profit percentage",
                default=0.5,
                min_value=0.1,
                max_value=2.0,
                step=0.1,
                category="exit",
                display_name="Target Profit %",
                order=2,
            ),
            "max_holding_bars": ParameterDefinition(
                name="max_holding_bars",
                param_type=ParameterType.INTEGER,
                description="Maximum holding period (bars)",
                default=10,
                min_value=1,
                max_value=50,
                category="exit",
                display_name="Max Holding Bars",
                order=3,
            ),
            "momentum_threshold": ParameterDefinition(
                name="momentum_threshold",
                param_type=ParameterType.PERCENTAGE,
                description="Momentum threshold for entry",
                default=0.3,
                min_value=0.0,
                max_value=2.0,
                step=0.1,
                category="entry",
                display_name="Momentum Threshold",
                order=4,
            ),
            "order_type": ParameterDefinition(
                name="order_type",
                param_type=ParameterType.CHOICE,
                description="Order type for entries",
                default="limit",
                choices=["market", "limit", "stop"],
                category="execution",
                display_name="Order Type",
                order=5,
            ),
        }
    
    @staticmethod
    def _momentum_schema() -> Dict[str, ParameterDefinition]:
        """Momentum parameter schema."""
        return {
            "momentum_period": ParameterDefinition(
                name="momentum_period",
                param_type=ParameterType.INTEGER,
                description="Momentum calculation period",
                default=14,
                min_value=5,
                max_value=50,
                category="indicators",
                display_name="Momentum Period",
                order=1,
            ),
            "momentum_threshold": ParameterDefinition(
                name="momentum_threshold",
                param_type=ParameterType.PERCENTAGE,
                description="Momentum threshold",
                default=2.0,
                min_value=0.0,
                max_value=10.0,
                step=0.1,
                category="entry",
                display_name="Momentum Threshold",
                order=2,
            ),
            "trend_period": ParameterDefinition(
                name="trend_period",
                param_type=ParameterType.INTEGER,
                description="Trend confirmation period",
                default=50,
                min_value=20,
                max_value=200,
                category="indicators",
                display_name="Trend Period",
                order=3,
            ),
            "momentum_type": ParameterDefinition(
                name="momentum_type",
                param_type=ParameterType.CHOICE,
                description="Type of momentum to use",
                default="price",
                choices=["price", "volume", "rsi", "macd", "combined"],
                category="strategy",
                display_name="Momentum Type",
                order=4,
            ),
            "direction": ParameterDefinition(
                name="direction",
                param_type=ParameterType.CHOICE,
                description="Trading direction",
                default="both",
                choices=["long_only", "short_only", "both"],
                category="strategy",
                display_name="Direction",
                order=5,
            ),
        }
    
    @staticmethod
    def _grid_schema() -> Dict[str, ParameterDefinition]:
        """Grid trading parameter schema."""
        return {
            "grid_type": ParameterDefinition(
                name="grid_type",
                param_type=ParameterType.CHOICE,
                description="Type of grid",
                default="fixed",
                choices=["fixed", "geometric", "fibonacci", "adaptive"],
                category="strategy",
                display_name="Grid Type",
                order=1,
            ),
            "num_levels": ParameterDefinition(
                name="num_levels",
                param_type=ParameterType.INTEGER,
                description="Number of grid levels",
                default=10,
                min_value=3,
                max_value=50,
                category="grid",
                display_name="Number of Levels",
                order=2,
            ),
            "grid_spacing": ParameterDefinition(
                name="grid_spacing",
                param_type=ParameterType.PERCENTAGE,
                description="Grid spacing percentage",
                default=1.0,
                min_value=0.1,
                max_value=10.0,
                step=0.1,
                category="grid",
                display_name="Grid Spacing %",
                order=3,
            ),
            "grid_range": ParameterDefinition(
                name="grid_range",
                param_type=ParameterType.PERCENTAGE,
                description="Grid range from center",
                default=10.0,
                min_value=1.0,
                max_value=50.0,
                step=0.5,
                category="grid",
                display_name="Grid Range %",
                order=4,
            ),
            "order_size": ParameterDefinition(
                name="order_size",
                param_type=ParameterType.FLOAT,
                description="Size per grid order",
                default=100.0,
                min_value=10.0,
                max_value=10000.0,
                category="execution",
                display_name="Order Size",
                order=5,
            ),
            "auto_rebalance": ParameterDefinition(
                name="auto_rebalance",
                param_type=ParameterType.BOOLEAN,
                description="Auto-rebalance grid",
                default=True,
                category="grid",
                display_name="Auto Rebalance",
                order=6,
            ),
        }
    
    @staticmethod
    def _ai_ensemble_schema() -> Dict[str, ParameterDefinition]:
        """AI ensemble parameter schema."""
        return {
            "ensemble_method": ParameterDefinition(
                name="ensemble_method",
                param_type=ParameterType.CHOICE,
                description="Ensemble combination method",
                default="weighted_vote",
                choices=["weighted_vote", "majority_vote", "average", "stacking", "dynamic"],
                category="ensemble",
                display_name="Ensemble Method",
                order=1,
            ),
            "weight_strategy": ParameterDefinition(
                name="weight_strategy",
                param_type=ParameterType.CHOICE,
                description="Weight allocation strategy",
                default="performance_based",
                choices=["equal", "performance_based", "recency_based", "confidence_based", "adaptive"],
                category="ensemble",
                display_name="Weight Strategy",
                order=2,
            ),
            "min_models": ParameterDefinition(
                name="min_models",
                param_type=ParameterType.INTEGER,
                description="Minimum number of models required",
                default=3,
                min_value=1,
                max_value=10,
                category="ensemble",
                display_name="Min Models",
                order=3,
            ),
            "confidence_threshold": ParameterDefinition(
                name="confidence_threshold",
                param_type=ParameterType.PERCENTAGE,
                description="Minimum confidence threshold",
                default=60.0,
                min_value=0.0,
                max_value=100.0,
                step=5.0,
                category="entry",
                display_name="Confidence Threshold %",
                order=4,
            ),
            "rebalance_interval": ParameterDefinition(
                name="rebalance_interval",
                param_type=ParameterType.INTEGER,
                description="Rebalance interval (predictions)",
                default=100,
                min_value=10,
                max_value=500,
                category="ensemble",
                display_name="Rebalance Interval",
                order=5,
            ),
        }
    
    @staticmethod
    def _martingale_schema() -> Dict[str, ParameterDefinition]:
        """Martingale parameter schema."""
        return {
            "martingale_type": ParameterDefinition(
                name="martingale_type",
                param_type=ParameterType.CHOICE,
                description="Type of martingale",
                default="classic",
                choices=["classic", "anti", "fibonacci", "dalembert", "risk_managed"],
                category="strategy",
                display_name="Martingale Type",
                order=1,
            ),
            "base_position_size": ParameterDefinition(
                name="base_position_size",
                param_type=ParameterType.FLOAT,
                description="Base position size",
                default=100.0,
                min_value=10.0,
                max_value=10000.0,
                category="execution",
                display_name="Base Position Size",
                order=2,
            ),
            "max_steps": ParameterDefinition(
                name="max_steps",
                param_type=ParameterType.INTEGER,
                description="Maximum number of steps",
                default=5,
                min_value=1,
                max_value=10,
                category="risk",
                display_name="Max Steps",
                order=3,
            ),
            "multiplier": ParameterDefinition(
                name="multiplier",
                param_type=ParameterType.FLOAT,
                description="Position size multiplier",
                default=2.0,
                min_value=1.0,
                max_value=5.0,
                step=0.1,
                category="execution",
                display_name="Multiplier",
                order=4,
            ),
            "direction": ParameterDefinition(
                name="direction",
                param_type=ParameterType.CHOICE,
                description="Trading direction",
                default="both",
                choices=["long", "short", "both"],
                category="strategy",
                display_name="Direction",
                order=5,
            ),
            "max_consecutive_losses": ParameterDefinition(
                name="max_consecutive_losses",
                param_type=ParameterType.INTEGER,
                description="Maximum consecutive losses allowed",
                default=5,
                min_value=1,
                max_value=10,
                category="risk",
                display_name="Max Consecutive Losses",
                order=6,
            ),
        }
    
    @staticmethod
    def _pairs_schema() -> Dict[str, ParameterDefinition]:
        """Pairs trading parameter schema."""
        return {
            "selection_method": ParameterDefinition(
                name="selection_method",
                param_type=ParameterType.CHOICE,
                description="Pair selection method",
                default="cointegration",
                choices=["cointegration", "correlation", "distance", "statistical"],
                category="strategy",
                display_name="Selection Method",
                order=1,
            ),
            "lookback_period": ParameterDefinition(
                name="lookback_period",
                param_type=ParameterType.INTEGER,
                description="Lookback period for analysis",
                default=100,
                min_value=30,
                max_value=300,
                category="indicators",
                display_name="Lookback Period",
                order=2,
            ),
            "min_correlation": ParameterDefinition(
                name="min_correlation",
                param_type=ParameterType.FLOAT,
                description="Minimum correlation for pairs",
                default=0.7,
                min_value=0.0,
                max_value=1.0,
                step=0.05,
                category="filters",
                display_name="Min Correlation",
                order=3,
            ),
            "entry_zscore": ParameterDefinition(
                name="entry_zscore",
                param_type=ParameterType.FLOAT,
                description="Entry Z-score threshold",
                default=2.0,
                min_value=0.5,
                max_value=4.0,
                step=0.1,
                category="entry",
                display_name="Entry Z-Score",
                order=4,
            ),
            "exit_zscore": ParameterDefinition(
                name="exit_zscore",
                param_type=ParameterType.FLOAT,
                description="Exit Z-score threshold",
                default=0.5,
                min_value=0.0,
                max_value=2.0,
                step=0.1,
                category="exit",
                display_name="Exit Z-Score",
                order=5,
            ),
            "max_holding_period": ParameterDefinition(
                name="max_holding_period",
                param_type=ParameterType.INTEGER,
                description="Maximum holding period (bars)",
                default=30,
                min_value=5,
                max_value=100,
                category="exit",
                display_name="Max Holding Period",
                order=6,
            ),
        }


# ============================================================================
# PARAMETER OPTIMIZER
# ============================================================================

class ParameterOptimizer:
    """
    Parameter optimization for strategies.
    
    Supports:
    - Grid search
    - Random search
    - Bayesian optimization
    - Genetic algorithm
    - Custom optimization
    """
    
    def __init__(
        self,
        param_set: ParameterSet,
        objective_fn: Callable[[Dict[str, Any]], float],
        optimization_method: str = "grid",
    ):
        """
        Initialize the parameter optimizer.
        
        Args:
            param_set: Parameter set to optimize
            objective_fn: Objective function to optimize
            optimization_method: Optimization method
        """
        self.param_set = param_set
        self.objective_fn = objective_fn
        self.optimization_method = optimization_method
        
        # Optimization state
        self.best_params: Optional[Dict[str, Any]] = None
        self.best_score: float = -float('inf')
        self.history: List[Dict[str, Any]] = []
        
        self.logger = logger
    
    def get_search_space(self) -> Dict[str, List[Any]]:
        """
        Get search space for parameters.
        
        Returns:
            Dict[str, List[Any]]: Search space by parameter
        """
        search_space = {}
        
        for name, definition in self.param_set.definitions.items():
            if definition.param_type == ParameterType.CHOICE:
                search_space[name] = definition.choices or []
            elif definition.param_type == ParameterType.MULTI_CHOICE:
                # For multi-choice, use combinations
                choices = definition.choices or []
                search_space[name] = choices
            elif definition.param_type == ParameterType.BOOLEAN:
                search_space[name] = [True, False]
            elif definition.param_type in [ParameterType.INTEGER, ParameterType.FLOAT]:
                min_val = definition.min_value or 0
                max_val = definition.max_value or 100
                step = definition.step or 1
                
                if self.optimization_method == "grid":
                    # Grid: use all values
                    values = []
                    current = min_val
                    while current <= max_val:
                        values.append(current)
                        current += step
                    search_space[name] = values
                else:
                    # For random/bayesian: use range
                    search_space[name] = (min_val, max_val, step)
            else:
                # Skip other types
                pass
        
        return search_space
    
    async def optimize(self, n_trials: int = 100) -> Dict[str, Any]:
        """
        Run optimization.
        
        Args:
            n_trials: Number of trials
            
        Returns:
            Dict[str, Any]: Best parameters
        """
        if self.optimization_method == "grid":
            return await self._grid_search()
        elif self.optimization_method == "random":
            return await self._random_search(n_trials)
        elif self.optimization_method == "bayesian":
            return await self._bayesian_search(n_trials)
        elif self.optimization_method == "genetic":
            return await self._genetic_search(n_trials)
        else:
            return await self._grid_search()
    
    async def _grid_search(self) -> Dict[str, Any]:
        """Grid search optimization."""
        search_space = self.get_search_space()
        
        # Get grid values
        grid_values = []
        param_names = []
        
        for name, space in search_space.items():
            if isinstance(space, list):
                grid_values.append(space)
                param_names.append(name)
        
        if not grid_values:
            return self.param_set.parameters
        
        # Generate grid combinations
        import itertools
        combinations = list(itertools.product(*grid_values))
        
        self.logger.info(f"Grid search: {len(combinations)} combinations")
        
        for combo in combinations:
            params = dict(zip(param_names, combo))
            score = await self._evaluate(params)
            
            if score > self.best_score:
                self.best_score = score
                self.best_params = params
            
            self.history.append({"params": params, "score": score})
        
        return self.best_params or self.param_set.parameters
    
    async def _random_search(self, n_trials: int) -> Dict[str, Any]:
        """Random search optimization."""
        search_space = self.get_search_space()
        
        for i in range(n_trials):
            params = {}
            
            for name, space in search_space.items():
                if isinstance(space, list):
                    params[name] = random.choice(space)
                elif isinstance(space, tuple):
                    min_val, max_val, step = space
                    if step >= 1:
                        params[name] = random.randint(int(min_val), int(max_val))
                    else:
                        params[name] = random.uniform(min_val, max_val)
            
            score = await self._evaluate(params)
            
            if score > self.best_score:
                self.best_score = score
                self.best_params = params
            
            self.history.append({"params": params, "score": score})
        
        return self.best_params or self.param_set.parameters
    
    async def _bayesian_search(self, n_trials: int) -> Dict[str, Any]:
        """Bayesian optimization."""
        # Simplified Bayesian optimization using random search
        # In production, this would use a proper Bayesian optimizer
        return await self._random_search(n_trials)
    
    async def _genetic_search(self, n_trials: int) -> Dict[str, Any]:
        """Genetic algorithm optimization."""
        # Simplified genetic algorithm
        return await self._random_search(n_trials)
    
    async def _evaluate(self, params: Dict[str, Any]) -> float:
        """
        Evaluate a parameter set.
        
        Args:
            params: Parameters to evaluate
            
        Returns:
            float: Objective score
        """
        try:
            score = await self.objective_fn(params)
            return float(score)
        except Exception as e:
            self.logger.error(f"Error evaluating parameters: {e}")
            return -float('inf')


# ============================================================================
# PARAMETER MANAGER
# ============================================================================

class ParameterManager:
    """
    Central manager for strategy parameters.
    
    Features:
    - Parameter storage and retrieval
    - Version management
    - Parameter validation
    - Optimization
    - Export/Import
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the parameter manager.
        
        Args:
            storage_path: Path for parameter storage
        """
        self.storage_path = storage_path
        self._param_sets: Dict[str, Dict[str, ParameterSet]] = {}
        self._lock = asyncio.Lock()
        self.logger = logger
    
    def register_schema(
        self,
        strategy_type: str,
        schema: Dict[str, ParameterDefinition],
    ) -> None:
        """
        Register a parameter schema.
        
        Args:
            strategy_type: Strategy type
            schema: Parameter definitions
        """
        # Store in a static registry
        pass
    
    def create_parameter_set(
        self,
        name: str,
        strategy_type: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ParameterSet:
        """
        Create a new parameter set.
        
        Args:
            name: Parameter set name
            strategy_type: Strategy type
            parameters: Initial parameters
            
        Returns:
            ParameterSet: Created parameter set
        """
        # Get schema
        schema = StrategyParameterSchema.get_schema(strategy_type)
        
        # Create definitions
        definitions = {}
        for defn_name, defn_data in schema.items():
            if isinstance(defn_data, ParameterDefinition):
                definitions[defn_name] = defn_data
            else:
                definitions[defn_name] = ParameterDefinition(**defn_data)
        
        # Create parameter set
        param_set = ParameterSet(
            name=name,
            parameters=parameters or {},
            definitions=definitions,
        )
        
        return param_set
    
    def save_parameter_set(self, param_set: ParameterSet) -> bool:
        """
        Save a parameter set.
        
        Args:
            param_set: Parameter set to save
            
        Returns:
            bool: True if saved successfully
        """
        try:
            if self.storage_path:
                import json
                data = param_set.to_dict()
                with open(f"{self.storage_path}/{param_set.name}.json", "w") as f:
                    json.dump(data, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving parameter set: {e}")
            return False
    
    def load_parameter_set(self, name: str) -> Optional[ParameterSet]:
        """
        Load a parameter set.
        
        Args:
            name: Parameter set name
            
        Returns:
            Optional[ParameterSet]: Loaded parameter set
        """
        try:
            if self.storage_path:
                import json
                with open(f"{self.storage_path}/{name}.json", "r") as f:
                    data = json.load(f)
                return ParameterSet.from_dict(data)
        except Exception as e:
            self.logger.error(f"Error loading parameter set: {e}")
            return None
    
    def get_parameter_set(
        self,
        name: str,
        strategy_type: str,
    ) -> ParameterSet:
        """
        Get or create a parameter set.
        
        Args:
            name: Parameter set name
            strategy_type: Strategy type
            
        Returns:
            ParameterSet: Parameter set
        """
        # Try to load existing
        param_set = self.load_parameter_set(name)
        if param_set:
            return param_set
        
        # Create new
        return self.create_parameter_set(name, strategy_type)
    
    async def optimize(
        self,
        param_set: ParameterSet,
        objective_fn: Callable[[Dict[str, Any]], float],
        method: str = "grid",
        n_trials: int = 100,
    ) -> Dict[str, Any]:
        """
        Optimize parameters.
        
        Args:
            param_set: Parameter set to optimize
            objective_fn: Objective function
            method: Optimization method
            n_trials: Number of trials
            
        Returns:
            Dict[str, Any]: Best parameters
        """
        optimizer = ParameterOptimizer(param_set, objective_fn, method)
        return await optimizer.optimize(n_trials)
    
    def validate_parameters(
        self,
        param_set: ParameterSet,
    ) -> List[str]:
        """
        Validate all parameters.
        
        Args:
            param_set: Parameter set to validate
            
        Returns:
            List[str]: Validation errors
        """
        return param_set.validate_all()
    
    def get_parameter_info(self) -> Dict[str, Any]:
        """
        Get information about available parameters.
        
        Returns:
            Dict[str, Any]: Parameter information
        """
        info = {}
        
        for strategy_type, schema in StrategyParameterSchema.__dict__.items():
            if strategy_type.endswith("_schema"):
                strategy_name = strategy_type.replace("_schema", "")
                schema = getattr(StrategyParameterSchema, strategy_type)()
                
                info[strategy_name] = {
                    "name": strategy_name,
                    "parameters": [
                        {
                            "name": name,
                            "type": defn.param_type.value,
                            "description": defn.description,
                            "default": defn.default,
                            "required": defn.required,
                            "min": defn.min_value,
                            "max": defn.max_value,
                            "choices": defn.choices,
                        }
                        for name, defn in schema.items()
                    ],
                }
        
        return info


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "ParameterType",
    "ParameterScope",
    "ParameterConstraint",
    
    # Models
    "ParameterDefinition",
    "ParameterSet",
    
    # Schemas
    "StrategyParameterSchema",
    
    # Optimizer
    "ParameterOptimizer",
    
    # Manager
    "ParameterManager",
]
