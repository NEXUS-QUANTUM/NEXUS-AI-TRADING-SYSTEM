"""
NEXUS AI TRADING SYSTEM - Signal Validator Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/signals/validator.py
Version: 1.0.0
Description: Advanced signal validation and filtering system
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable, Tuple, Set
from collections import deque

from pydantic import BaseModel, Field, ConfigDict, validator, root_validator

from shared.types.trading import OrderSide, OrderType, OrderStatus, TimeInForce
from shared.helpers.trading_helpers import (
    calculate_percentage_change,
    calculate_price_distance,
    round_to_tick_size,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr,
    calculate_vwap
)
from shared.constants.trading_constants import (
    MIN_VALID_SIGNAL_STRENGTH,
    MAX_SIGNAL_AGE,
    SIGNAL_VALIDATION_TIMEOUT
)
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class SignalValidationLevel(str, Enum):
    """Signal validation levels"""
    BASIC = "basic"                      # Basic validation (price, volume)
    STANDARD = "standard"                # Standard validation with indicators
    ADVANCED = "advanced"                # Advanced validation with ML
    STRICT = "strict"                    # Strict validation with all checks
    CUSTOM = "custom"                    # Custom validation rules


class SignalQuality(str, Enum):
    """Signal quality ratings"""
    EXCELLENT = "excellent"              # Excellent quality
    GOOD = "good"                        # Good quality
    FAIR = "fair"                        # Fair quality
    POOR = "poor"                        # Poor quality
    INVALID = "invalid"                  # Invalid signal


class ValidationRuleType(str, Enum):
    """Types of validation rules"""
    PRICE = "price"                      # Price-based rules
    VOLUME = "volume"                    # Volume-based rules
    INDICATOR = "indicator"              # Indicator-based rules
    PATTERN = "pattern"                  # Pattern-based rules
    TIME = "time"                        # Time-based rules
    RISK = "risk"                        # Risk-based rules
    MARKET = "market"                    # Market-based rules
    CUSTOM = "custom"                    # Custom rules


class ValidationResult(BaseModel):
    """Validation result"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    is_valid: bool = Field(..., description="Whether signal is valid")
    quality: SignalQuality = Field(..., description="Signal quality rating")
    confidence: float = Field(..., description="Confidence score (0-100)")
    score: float = Field(..., description="Overall validation score (0-100)")
    
    # Validation details
    passed_rules: List[str] = Field(default_factory=list, description="Passed validation rules")
    failed_rules: List[str] = Field(default_factory=list, description="Failed validation rules")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    
    # Metrics
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Validation metrics")
    
    # Additional data
    data: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Validation timestamp")
    duration_ms: float = Field(0.0, description="Validation duration in milliseconds")


class ValidationRule(BaseModel):
    """Individual validation rule"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    rule_type: ValidationRuleType = Field(..., description="Rule type")
    name: str = Field(..., description="Rule name")
    description: str = Field("", description="Rule description")
    
    # Rule parameters
    params: Dict[str, Any] = Field(default_factory=dict, description="Rule parameters")
    
    # Rule logic
    condition: str = Field(..., description="Condition expression")
    check_function: Optional[Callable] = Field(None, description="Check function")
    
    # Rule configuration
    required: bool = Field(True, description="Whether rule is required")
    weight: float = Field(1.0, description="Rule weight")
    threshold: float = Field(0.0, description="Rule threshold")
    
    # Error handling
    error_message: str = Field("", description="Error message")
    warning_message: str = Field("", description="Warning message")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Rule tags")
    enabled: bool = Field(True, description="Whether rule is enabled")


class SignalValidatorConfig(BaseModel):
    """Configuration for signal validator"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    validation_level: SignalValidationLevel = Field(default=SignalValidationLevel.STANDARD)
    min_confidence: float = Field(50.0, description="Minimum confidence score")
    min_score: float = Field(60.0, description="Minimum validation score")
    
    # Rule configuration
    rules: List[ValidationRule] = Field(default_factory=list, description="Validation rules")
    custom_rules: List[ValidationRule] = Field(default_factory=list, description="Custom validation rules")
    enabled_rules: List[str] = Field(default_factory=list, description="Enabled rule names")
    disabled_rules: List[str] = Field(default_factory=list, description="Disabled rule names")
    
    # Price validation
    min_price: float = Field(0.0, description="Minimum price")
    max_price: float = Field(float('inf'), description="Maximum price")
    min_price_change: float = Field(0.0, description="Minimum price change %")
    max_price_change: float = Field(100.0, description="Maximum price change %")
    check_price_volatility: bool = Field(True, description="Check price volatility")
    max_volatility: float = Field(50.0, description="Maximum volatility %")
    
    # Volume validation
    min_volume: float = Field(0.0, description="Minimum volume")
    min_volume_ratio: float = Field(0.5, description="Minimum volume ratio to average")
    max_volume_ratio: float = Field(10.0, description="Maximum volume ratio to average")
    check_volume_spike: bool = Field(True, description="Check for volume spikes")
    volume_spike_threshold: float = Field(5.0, description="Volume spike threshold")
    
    # Indicator validation
    check_rsi: bool = Field(True, description="Check RSI")
    rsi_oversold: float = Field(30.0, description="RSI oversold threshold")
    rsi_overbought: float = Field(70.0, description="RSI overbought threshold")
    
    check_macd: bool = Field(True, description="Check MACD")
    macd_threshold: float = Field(0.01, description="MACD threshold")
    
    check_bollinger: bool = Field(True, description="Check Bollinger Bands")
    bollinger_deviation: float = Field(1.5, description="Bollinger deviation threshold")
    
    # Time validation
    max_age: int = Field(MAX_SIGNAL_AGE, description="Maximum signal age in seconds")
    check_trading_hours: bool = Field(False, description="Check trading hours")
    trading_hours_start: str = Field("09:30", description="Trading hours start")
    trading_hours_end: str = Field("16:00", description="Trading hours end")
    
    # Risk validation
    check_risk_reward: bool = Field(True, description="Check risk-reward ratio")
    min_risk_reward: float = Field(1.5, description="Minimum risk-reward ratio")
    max_risk_percent: float = Field(2.0, description="Maximum risk percentage")
    
    # Market validation
    check_market_conditions: bool = Field(True, description="Check market conditions")
    check_spread: bool = Field(True, description="Check spread")
    max_spread: float = Field(0.005, description="Maximum spread")
    check_slippage: bool = Field(True, description="Check slippage")
    max_slippage: float = Field(0.01, description="Maximum slippage")
    
    # Pattern validation
    check_candle_patterns: bool = Field(True, description="Check candle patterns")
    check_chart_patterns: bool = Field(True, description="Check chart patterns")
    min_pattern_strength: float = Field(0.3, description="Minimum pattern strength")
    
    # Performance
    timeout: float = Field(SIGNAL_VALIDATION_TIMEOUT, description="Validation timeout in seconds")
    cache_results: bool = Field(True, description="Cache validation results")
    cache_ttl: int = Field(60, description="Cache TTL in seconds")
    
    # Advanced
    require_multiple_confirmations: bool = Field(False, description="Require multiple confirmations")
    min_confirmations: int = Field(3, description="Minimum confirmations")
    use_ml_validation: bool = Field(False, description="Use ML validation")
    ml_model_path: Optional[str] = Field(None, description="ML model path")


class SignalValidator:
    """
    Advanced signal validation system.
    
    Features:
    - Multiple validation levels (Basic, Standard, Advanced, Strict)
    - Configurable validation rules
    - Price, volume, indicator, time, risk, market validation
    - Pattern recognition validation
    - Quality scoring
    - Confidence scoring
    - Rule-based validation
    - Custom rule support
    - Performance metrics
    - Caching support
    """

    def __init__(
        self,
        config: Optional[SignalValidatorConfig] = None,
        broker: Optional[Any] = None,
        market_data: Optional[Any] = None
    ):
        """
        Initialize the signal validator.

        Args:
            config: Validator configuration
            broker: Broker interface for market data
            market_data: Market data provider
        """
        self.config = config or SignalValidatorConfig()
        self._broker = broker
        self._market_data = market_data
        
        # Rule storage
        self._rules: List[ValidationRule] = []
        self._rule_map: Dict[str, ValidationRule] = {}
        self._custom_rules: List[ValidationRule] = []
        
        # Cache
        self._cache: Dict[str, Tuple[ValidationResult, datetime]] = {}
        
        # Metrics
        self._validation_count: int = 0
        self._valid_count: int = 0
        self._invalid_count: int = 0
        self._avg_validation_time: float = 0.0
        self._validation_history: deque = deque(maxlen=1000)
        
        # Price history for indicators
        self._price_history: List[float] = []
        self._volume_history: List[float] = []
        self._timestamp_history: List[datetime] = []
        self._max_history_length = 1000
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Initialize rules
        self._initialize_rules()
        
        logger.info(f"Initialized SignalValidator with level: {self.config.validation_level.value}")

    def _initialize_rules(self):
        """Initialize validation rules based on configuration"""
        rules = []
        
        # Basic validation rules
        rules.extend(self._get_basic_rules())
        
        # Standard validation rules
        if self.config.validation_level in [SignalValidationLevel.STANDARD, 
                                             SignalValidationLevel.ADVANCED,
                                             SignalValidationLevel.STRICT]:
            rules.extend(self._get_standard_rules())
        
        # Advanced validation rules
        if self.config.validation_level in [SignalValidationLevel.ADVANCED,
                                             SignalValidationLevel.STRICT]:
            rules.extend(self._get_advanced_rules())
        
        # Strict validation rules
        if self.config.validation_level == SignalValidationLevel.STRICT:
            rules.extend(self._get_strict_rules())
        
        # Add custom rules
        if self.config.custom_rules:
            rules.extend(self.config.custom_rules)
        
        # Apply enabled/disabled rules
        if self.config.enabled_rules:
            enabled_set = set(self.config.enabled_rules)
            rules = [r for r in rules if r.name in enabled_set]
        
        if self.config.disabled_rules:
            disabled_set = set(self.config.disabled_rules)
            rules = [r for r in rules if r.name not in disabled_set]
        
        # Store rules
        self._rules = rules
        self._rule_map = {r.name: r for r in rules}
        
        logger.info(f"Initialized {len(rules)} validation rules")

    def _get_basic_rules(self) -> List[ValidationRule]:
        """Get basic validation rules"""
        return [
            ValidationRule(
                rule_type=ValidationRuleType.PRICE,
                name="price_valid",
                description="Price is valid",
                condition="price > 0 and price < inf",
                weight=2.0,
                error_message="Invalid price"
            ),
            ValidationRule(
                rule_type=ValidationRuleType.PRICE,
                name="price_min",
                description="Price is above minimum",
                condition="price >= min_price",
                params={"min_price": self.config.min_price},
                weight=1.0,
                error_message=f"Price below minimum {self.config.min_price}"
            ),
            ValidationRule(
                rule_type=ValidationRuleType.PRICE,
                name="price_max",
                description="Price is below maximum",
                condition="price <= max_price",
                params={"max_price": self.config.max_price},
                weight=1.0,
                error_message=f"Price above maximum {self.config.max_price}"
            ),
            ValidationRule(
                rule_type=ValidationRuleType.VOLUME,
                name="volume_valid",
                description="Volume is valid",
                condition="volume > 0",
                weight=1.5,
                error_message="Invalid volume"
            ),
            ValidationRule(
                rule_type=ValidationRuleType.VOLUME,
                name="volume_min",
                description="Volume is above minimum",
                condition="volume >= min_volume",
                params={"min_volume": self.config.min_volume},
                weight=1.0,
                error_message=f"Volume below minimum {self.config.min_volume}"
            )
        ]

    def _get_standard_rules(self) -> List[ValidationRule]:
        """Get standard validation rules"""
        rules = []
        
        # Price change validation
        if self.config.min_price_change > 0 or self.config.max_price_change < 100:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.PRICE,
                    name="price_change",
                    description="Price change within limits",
                    condition="abs(price_change) >= min_price_change and abs(price_change) <= max_price_change",
                    params={
                        "min_price_change": self.config.min_price_change,
                        "max_price_change": self.config.max_price_change
                    },
                    weight=1.5,
                    error_message=f"Price change outside limits ({self.config.min_price_change}% - {self.config.max_price_change}%)"
                )
            )
        
        # Volume ratio validation
        if self.config.min_volume_ratio > 0:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.VOLUME,
                    name="volume_ratio",
                    description="Volume ratio within limits",
                    condition="volume_ratio >= min_volume_ratio and volume_ratio <= max_volume_ratio",
                    params={
                        "min_volume_ratio": self.config.min_volume_ratio,
                        "max_volume_ratio": self.config.max_volume_ratio
                    },
                    weight=1.0,
                    error_message=f"Volume ratio outside limits ({self.config.min_volume_ratio} - {self.config.max_volume_ratio})"
                )
            )
        
        # RSI validation
        if self.config.check_rsi:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.INDICATOR,
                    name="rsi_valid",
                    description="RSI not in extreme zones",
                    condition="rsi > rsi_oversold and rsi < rsi_overbought",
                    params={
                        "rsi_oversold": self.config.rsi_oversold,
                        "rsi_overbought": self.config.rsi_overbought
                    },
                    weight=0.5,
                    warning_message=f"RSI in extreme zone ({self.config.rsi_oversold} - {self.config.rsi_overbought})"
                )
            )
        
        # MACD validation
        if self.config.check_macd:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.INDICATOR,
                    name="macd_valid",
                    description="MACD within limits",
                    condition="abs(macd_histogram) >= macd_threshold",
                    params={"macd_threshold": self.config.macd_threshold},
                    weight=0.5,
                    warning_message=f"MACD below threshold {self.config.macd_threshold}"
                )
            )
        
        # Bollinger Bands validation
        if self.config.check_bollinger:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.INDICATOR,
                    name="bollinger_valid",
                    description="Price within Bollinger Bands",
                    condition="price >= bollinger_lower and price <= bollinger_upper",
                    weight=0.5,
                    warning_message="Price outside Bollinger Bands"
                )
            )
        
        return rules

    def _get_advanced_rules(self) -> List[ValidationRule]:
        """Get advanced validation rules"""
        rules = []
        
        # Risk-reward validation
        if self.config.check_risk_reward:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.RISK,
                    name="risk_reward",
                    description="Risk-reward ratio is sufficient",
                    condition="risk_reward_ratio >= min_risk_reward",
                    params={"min_risk_reward": self.config.min_risk_reward},
                    weight=2.0,
                    error_message=f"Risk-reward ratio below {self.config.min_risk_reward}"
                )
            )
        
        # Spread validation
        if self.config.check_spread:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.MARKET,
                    name="spread_valid",
                    description="Spread is acceptable",
                    condition="spread <= max_spread",
                    params={"max_spread": self.config.max_spread},
                    weight=1.0,
                    error_message=f"Spread above {self.config.max_spread}"
                )
            )
        
        # Slippage validation
        if self.config.check_slippage:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.MARKET,
                    name="slippage_valid",
                    description="Slippage is acceptable",
                    condition="slippage <= max_slippage",
                    params={"max_slippage": self.config.max_slippage},
                    weight=0.5,
                    warning_message=f"Slippage above {self.config.max_slippage}"
                )
            )
        
        # Time validation
        if self.config.max_age > 0:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.TIME,
                    name="age_valid",
                    description="Signal is fresh",
                    condition="age <= max_age",
                    params={"max_age": self.config.max_age},
                    weight=1.0,
                    error_message=f"Signal age exceeds {self.config.max_age}s"
                )
            )
        
        return rules

    def _get_strict_rules(self) -> List[ValidationRule]:
        """Get strict validation rules"""
        rules = []
        
        # Multiple confirmations
        if self.config.require_multiple_confirmations:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.PATTERN,
                    name="confirmations",
                    description="Multiple confirmations required",
                    condition="confirmations >= min_confirmations",
                    params={"min_confirmations": self.config.min_confirmations},
                    weight=3.0,
                    error_message=f"Need {self.config.min_confirmations} confirmations"
                )
            )
        
        # Pattern strength
        if self.config.check_candle_patterns or self.config.check_chart_patterns:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.PATTERN,
                    name="pattern_strength",
                    description="Pattern strength is sufficient",
                    condition="pattern_strength >= min_pattern_strength",
                    params={"min_pattern_strength": self.config.min_pattern_strength},
                    weight=1.0,
                    warning_message=f"Pattern strength below {self.config.min_pattern_strength}"
                )
            )
        
        # Price volatility
        if self.config.check_price_volatility:
            rules.append(
                ValidationRule(
                    rule_type=ValidationRuleType.PRICE,
                    name="volatility",
                    description="Volatility within limits",
                    condition="volatility <= max_volatility",
                    params={"max_volatility": self.config.max_volatility},
                    weight=0.5,
                    warning_message=f"Volatility above {self.config.max_volatility}%"
                )
            )
        
        return rules

    async def validate(self, signal: Dict[str, Any]) -> ValidationResult:
        """
        Validate a trading signal.

        Args:
            signal: Signal data to validate

        Returns:
            ValidationResult: Validation result
        """
        start_time = datetime.utcnow()
        
        # Check cache
        if self.config.cache_results:
            cache_key = self._get_cache_key(signal)
            cached = self._cache.get(cache_key)
            if cached:
                result, timestamp = cached
                if (datetime.utcnow() - timestamp).total_seconds() < self.config.cache_ttl:
                    return result
        
        # Prepare validation context
        context = await self._prepare_validation_context(signal)
        
        # Execute validation
        passed_rules = []
        failed_rules = []
        warnings = []
        errors = []
        total_score = 0
        total_weight = 0
        
        async with self._lock:
            for rule in self._rules:
                if not rule.enabled:
                    continue
                
                try:
                    result = await self._evaluate_rule(rule, context)
                    
                    if result['passed']:
                        passed_rules.append(rule.name)
                        total_score += rule.weight
                    else:
                        if rule.required:
                            failed_rules.append(rule.name)
                            errors.append(rule.error_message or f"Failed: {rule.name}")
                        else:
                            warnings.append(rule.warning_message or f"Warning: {rule.name}")
                    
                    total_weight += rule.weight
                    
                except Exception as e:
                    logger.error(f"Error evaluating rule {rule.name}: {e}")
                    errors.append(f"Error evaluating {rule.name}: {e}")
            
            # Calculate scores
            if total_weight > 0:
                score = (total_score / total_weight) * 100
            else:
                score = 0
            
            confidence = self._calculate_confidence(score, passed_rules, failed_rules)
            quality = self._get_quality_rating(score, confidence, failed_rules)
            
            # Determine validity
            is_valid = (
                score >= self.config.min_score and
                confidence >= self.config.min_confidence and
                not errors and
                len(failed_rules) == 0
            )
            
            # Create result
            result = ValidationResult(
                is_valid=is_valid,
                quality=quality,
                confidence=confidence,
                score=score,
                passed_rules=passed_rules,
                failed_rules=failed_rules,
                warnings=warnings,
                errors=errors,
                metrics=self._calculate_metrics(context),
                data={'signal': signal}
            )
        
        # Update metrics
        self._update_metrics(result, start_time)
        
        # Cache result
        if self.config.cache_results:
            cache_key = self._get_cache_key(signal)
            self._cache[cache_key] = (result, datetime.utcnow())
        
        return result

    async def _prepare_validation_context(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare validation context with market data.

        Args:
            signal: Signal data

        Returns:
            Dict[str, Any]: Validation context
        """
        context = signal.copy()
        
        # Add current market data
        if self._broker:
            try:
                ticker = await self._broker.get_ticker(signal.get('symbol', ''))
                if ticker:
                    context['current_price'] = ticker.get('last', 0)
                    context['bid'] = ticker.get('bid', 0)
                    context['ask'] = ticker.get('ask', 0)
                    context['volume'] = ticker.get('volume', 0)
                    
                    # Calculate spread
                    if context.get('bid') and context.get('ask'):
                        context['spread'] = (context['ask'] - context['bid']) / context['bid']
            except Exception as e:
                logger.warning(f"Failed to get market data: {e}")
        
        # Calculate indicators
        if self._price_history:
            context['rsi'] = calculate_rsi(self._price_history, 14)
            macd = calculate_macd(self._price_history, 12, 26, 9)
            if macd:
                context['macd_histogram'] = macd.get('histogram', 0)
            
            bb = calculate_bollinger_bands(self._price_history, 20, 2)
            if bb:
                context['bollinger_upper'] = bb.get('upper', 0)
                context['bollinger_lower'] = bb.get('lower', 0)
            
            context['atr'] = calculate_atr(self._price_history, 14)
            context['vwap'] = calculate_vwap(self._price_history, self._volume_history)
        
        # Calculate price change
        if context.get('price') and context.get('current_price'):
            context['price_change'] = calculate_percentage_change(
                context['price'], 
                context['current_price']
            )
        
        # Calculate volume ratio
        if context.get('volume') and self._volume_history:
            avg_volume = sum(self._volume_history[-20:]) / min(20, len(self._volume_history))
            if avg_volume > 0:
                context['volume_ratio'] = context['volume'] / avg_volume
        
        # Calculate age
        if signal.get('timestamp'):
            context['age'] = (datetime.utcnow() - signal['timestamp']).total_seconds()
        
        # Calculate risk-reward
        if signal.get('entry_price') and signal.get('stop_loss') and signal.get('take_profit'):
            risk = abs(signal['entry_price'] - signal['stop_loss'])
            reward = abs(signal['take_profit'] - signal['entry_price'])
            if risk > 0:
                context['risk_reward_ratio'] = reward / risk
        
        return context

    async def _evaluate_rule(self, rule: ValidationRule, context: Dict[str, Any]) -> Dict[str, bool]:
        """
        Evaluate a single validation rule.

        Args:
            rule: Validation rule
            context: Validation context

        Returns:
            Dict[str, bool]: Evaluation result
        """
        if rule.check_function:
            # Use custom check function
            if asyncio.iscoroutinefunction(rule.check_function):
                passed = await rule.check_function(context)
            else:
                passed = rule.check_function(context)
        else:
            # Evaluate condition expression
            passed = self._evaluate_condition(rule.condition, rule.params, context)
        
        return {'passed': passed}

    def _evaluate_condition(self, condition: str, params: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition expression.

        Args:
            condition: Condition expression
            params: Rule parameters
            context: Validation context

        Returns:
            bool: Whether condition is met
        """
        try:
            # Prepare safe evaluation environment
            safe_globals = {
                'abs': abs,
                'min': min,
                'max': max,
                'sum': sum,
                'len': len,
                'float': float,
                'int': int,
                'str': str,
                'bool': bool,
                'True': True,
                'False': False,
                'None': None,
                'inf': float('inf'),
                'math': __import__('math')
            }
            
            # Add context and params to namespace
            namespace = {**context, **params, **safe_globals}
            
            # Evaluate condition safely
            result = eval(condition, {"__builtins__": {}}, namespace)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False

    def _calculate_confidence(self, score: float, passed_rules: List[str], failed_rules: List[str]) -> float:
        """
        Calculate confidence score.

        Args:
            score: Validation score
            passed_rules: Passed rules
            failed_rules: Failed rules

        Returns:
            float: Confidence score (0-100)
        """
        # Base confidence from score
        confidence = score * 0.6
        
        # Penalty for failed rules
        failed_penalty = len(failed_rules) * 5
        confidence -= failed_penalty
        
        # Bonus for passed rules
        passed_bonus = min(len(passed_rules) * 2, 20)
        confidence += passed_bonus
        
        # Ensure range
        return max(0, min(100, confidence))

    def _get_quality_rating(self, score: float, confidence: float, failed_rules: List[str]) -> SignalQuality:
        """
        Get quality rating based on scores.

        Args:
            score: Validation score
            confidence: Confidence score
            failed_rules: Failed rules

        Returns:
            SignalQuality: Quality rating
        """
        if failed_rules and len(failed_rules) > 0:
            return SignalQuality.INVALID
        
        avg_score = (score + confidence) / 2
        
        if avg_score >= 90:
            return SignalQuality.EXCELLENT
        elif avg_score >= 75:
            return SignalQuality.GOOD
        elif avg_score >= 60:
            return SignalQuality.FAIR
        else:
            return SignalQuality.POOR

    def _calculate_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate validation metrics.

        Args:
            context: Validation context

        Returns:
            Dict[str, Any]: Metrics
        """
        metrics = {}
        
        # Price metrics
        if context.get('price'):
            metrics['price'] = context['price']
        if context.get('current_price'):
            metrics['current_price'] = context['current_price']
        if context.get('price_change') is not None:
            metrics['price_change'] = context['price_change']
        
        # Volume metrics
        if context.get('volume'):
            metrics['volume'] = context['volume']
        if context.get('volume_ratio'):
            metrics['volume_ratio'] = context['volume_ratio']
        
        # Indicator metrics
        if context.get('rsi') is not None:
            metrics['rsi'] = context['rsi']
        if context.get('macd_histogram') is not None:
            metrics['macd_histogram'] = context['macd_histogram']
        if context.get('atr') is not None:
            metrics['atr'] = context['atr']
        
        # Risk metrics
        if context.get('risk_reward_ratio') is not None:
            metrics['risk_reward_ratio'] = context['risk_reward_ratio']
        if context.get('spread') is not None:
            metrics['spread'] = context['spread']
        
        # Time metrics
        if context.get('age') is not None:
            metrics['age'] = context['age']
        
        return metrics

    def _update_metrics(self, result: ValidationResult, start_time: datetime):
        """
        Update validator metrics.

        Args:
            result: Validation result
            start_time: Start time
        """
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        self._validation_count += 1
        if result.is_valid:
            self._valid_count += 1
        else:
            self._invalid_count += 1
        
        self._avg_validation_time = (
            (self._avg_validation_time * (self._validation_count - 1) + duration) /
            self._validation_count
        )
        
        self._validation_history.append({
            'timestamp': datetime.utcnow(),
            'is_valid': result.is_valid,
            'score': result.score,
            'confidence': result.confidence,
            'duration_ms': duration
        })

    def _get_cache_key(self, signal: Dict[str, Any]) -> str:
        """
        Generate cache key for signal.

        Args:
            signal: Signal data

        Returns:
            str: Cache key
        """
        # Use symbol, price, and timestamp for cache key
        symbol = signal.get('symbol', '')
        price = signal.get('price', 0)
        timestamp = signal.get('timestamp', datetime.utcnow())
        return f"{symbol}:{price}:{timestamp.isoformat() if timestamp else ''}"

    async def add_custom_rule(self, rule: ValidationRule) -> bool:
        """
        Add a custom validation rule.

        Args:
            rule: Custom rule

        Returns:
            bool: True if added successfully
        """
        async with self._lock:
            if rule.name in self._rule_map:
                logger.warning(f"Rule {rule.name} already exists")
                return False
            
            self._custom_rules.append(rule)
            self._rules.append(rule)
            self._rule_map[rule.name] = rule
            
            logger.info(f"Added custom rule: {rule.name}")
            return True

    async def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a validation rule.

        Args:
            rule_name: Rule name

        Returns:
            bool: True if removed successfully
        """
        async with self._lock:
            if rule_name not in self._rule_map:
                return False
            
            self._rules = [r for r in self._rules if r.name != rule_name]
            self._custom_rules = [r for r in self._custom_rules if r.name != rule_name]
            del self._rule_map[rule_name]
            
            logger.info(f"Removed rule: {rule_name}")
            return True

    async def enable_rule(self, rule_name: str) -> bool:
        """
        Enable a validation rule.

        Args:
            rule_name: Rule name

        Returns:
            bool: True if enabled successfully
        """
        rule = self._rule_map.get(rule_name)
        if not rule:
            return False
        
        rule.enabled = True
        return True

    async def disable_rule(self, rule_name: str) -> bool:
        """
        Disable a validation rule.

        Args:
            rule_name: Rule name

        Returns:
            bool: True if disabled successfully
        """
        rule = self._rule_map.get(rule_name)
        if not rule:
            return False
        
        rule.enabled = False
        return True

    async def get_rule(self, rule_name: str) -> Optional[ValidationRule]:
        """
        Get a validation rule.

        Args:
            rule_name: Rule name

        Returns:
            Optional[ValidationRule]: Validation rule
        """
        return self._rule_map.get(rule_name)

    async def get_rules(self, rule_type: Optional[ValidationRuleType] = None) -> List[ValidationRule]:
        """
        Get validation rules.

        Args:
            rule_type: Filter by rule type

        Returns:
            List[ValidationRule]: Validation rules
        """
        if rule_type:
            return [r for r in self._rules if r.rule_type == rule_type]
        return self._rules.copy()

    async def update_price_history(self, prices: List[float], volumes: Optional[List[float]] = None):
        """
        Update price history for indicator calculations.

        Args:
            prices: Price history
            volumes: Optional volume history
        """
        async with self._lock:
            self._price_history = prices[-self._max_history_length:]
            if volumes:
                self._volume_history = volumes[-self._max_history_length:]

    async def clear_cache(self):
        """Clear validation cache."""
        async with self._lock:
            self._cache.clear()
            logger.info("Validation cache cleared")

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get validation statistics.

        Returns:
            Dict[str, Any]: Statistics
        """
        async with self._lock:
            return {
                'total_validations': self._validation_count,
                'valid_count': self._valid_count,
                'invalid_count': self._invalid_count,
                'success_rate': (self._valid_count / self._validation_count * 100) if self._validation_count > 0 else 0,
                'avg_validation_time_ms': self._avg_validation_time,
                'total_rules': len(self._rules),
                'enabled_rules': len([r for r in self._rules if r.enabled]),
                'custom_rules': len(self._custom_rules),
                'cache_size': len(self._cache),
                'history_size': len(self._validation_history)
            }

    async def export_rules(self) -> List[Dict[str, Any]]:
        """
        Export validation rules.

        Returns:
            List[Dict[str, Any]]: Exported rules
        """
        return [r.model_dump() for r in self._rules]

    async def import_rules(self, rules_data: List[Dict[str, Any]]) -> int:
        """
        Import validation rules.

        Args:
            rules_data: Rules data

        Returns:
            int: Number of rules imported
        """
        imported = 0
        for rule_data in rules_data:
            try:
                rule = ValidationRule(**rule_data)
                await self.add_custom_rule(rule)
                imported += 1
            except Exception as e:
                logger.error(f"Failed to import rule: {e}")
        
        return imported

    async def validate_batch(self, signals: List[Dict[str, Any]]) -> List[ValidationResult]:
        """
        Validate multiple signals in batch.

        Args:
            signals: List of signals

        Returns:
            List[ValidationResult]: Validation results
        """
        results = []
        for signal in signals:
            result = await self.validate(signal)
            results.append(result)
        return results

    async def filter_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter signals by validation.

        Args:
            signals: List of signals

        Returns:
            List[Dict[str, Any]]: Valid signals
        """
        valid_signals = []
        for signal in signals:
            result = await self.validate(signal)
            if result.is_valid:
                # Add validation data to signal
                signal['validation'] = result.model_dump()
                valid_signals.append(signal)
        return valid_signals

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.clear_cache()

    def __repr__(self) -> str:
        return f"<SignalValidator level={self.config.validation_level.value} rules={len(self._rules)}>"
