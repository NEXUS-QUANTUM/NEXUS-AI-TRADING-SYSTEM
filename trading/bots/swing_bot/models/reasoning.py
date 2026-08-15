"""
Swing Bot Reasoning Model
===========================

This module provides reasoning and decision-making models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ReasoningRule:
    """Reasoning rule data structure."""
    rule_id: str
    name: str
    condition: Dict[str, Any]
    action: Dict[str, Any]
    priority: int
    confidence: float
    status: str = 'active'  # 'active', 'inactive'


@dataclass
class ReasoningResult:
    """Reasoning result data structure."""
    timestamp: datetime
    rules_applied: List[str]
    conclusion: str
    confidence: float
    evidence: Dict[str, Any]
    recommendation: Optional[Dict[str, Any]] = None


@dataclass
class ReasoningSignal:
    """Reasoning trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    reasoning: ReasoningResult
    indicators: Dict[str, Any] = field(default_factory=dict)


class ReasoningModel:
    """
    Reasoning and decision-making model for trading.
    
    Implements rule-based and probabilistic reasoning.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the reasoning model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.rules: Dict[str, ReasoningRule] = {}
        self.results: List[ReasoningResult] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Register default rules
        self._register_default_rules()
        
    def _register_default_rules(self) -> None:
        """Register default reasoning rules."""
        default_rules = [
            ReasoningRule(
                rule_id='rule_001',
                name='bullish_trend',
                condition={
                    'type': 'and',
                    'conditions': [
                        {'type': 'price_above_ma', 'ma_period': 50},
                        {'type': 'momentum_positive', 'period': 20}
                    ]
                },
                action={
                    'type': 'buy',
                    'confidence': 0.7,
                    'reason': 'Bullish trend detected'
                },
                priority=1,
                confidence=0.8
            ),
            ReasoningRule(
                rule_id='rule_002',
                name='bearish_trend',
                condition={
                    'type': 'and',
                    'conditions': [
                        {'type': 'price_below_ma', 'ma_period': 50},
                        {'type': 'momentum_negative', 'period': 20}
                    ]
                },
                action={
                    'type': 'sell',
                    'confidence': 0.7,
                    'reason': 'Bearish trend detected'
                },
                priority=1,
                confidence=0.8
            ),
            ReasoningRule(
                rule_id='rule_003',
                name='oversold_bounce',
                condition={
                    'type': 'and',
                    'conditions': [
                        {'type': 'rsi_oversold', 'threshold': 30},
                        {'type': 'price_support', 'lookback': 50}
                    ]
                },
                action={
                    'type': 'buy',
                    'confidence': 0.6,
                    'reason': 'Oversold bounce potential'
                },
                priority=2,
                confidence=0.7
            ),
            ReasoningRule(
                rule_id='rule_004',
                name='overbought_reversal',
                condition={
                    'type': 'and',
                    'conditions': [
                        {'type': 'rsi_overbought', 'threshold': 70},
                        {'type': 'price_resistance', 'lookback': 50}
                    ]
                },
                action={
                    'type': 'sell',
                    'confidence': 0.6,
                    'reason': 'Overbought reversal potential'
                },
                priority=2,
                confidence=0.7
            ),
            ReasoningRule(
                rule_id='rule_005',
                name='breakout_confirmation',
                condition={
                    'type': 'and',
                    'conditions': [
                        {'type': 'price_breakout', 'threshold': 0.02},
                        {'type': 'volume_spike', 'threshold': 1.5}
                    ]
                },
                action={
                    'type': 'buy',
                    'confidence': 0.8,
                    'reason': 'Breakout confirmed with volume'
                },
                priority=1,
                confidence=0.9
            )
        ]
        
        for rule in default_rules:
            self.rules[rule.rule_id] = rule
    
    def add_rule(self, rule: ReasoningRule) -> None:
        """
        Add a reasoning rule.
        
        Args:
            rule: ReasoningRule object
        """
        self.rules[rule.rule_id] = rule
    
    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a reasoning rule.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            True if removed, False otherwise
        """
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False
    
    def reason(self, df: pd.DataFrame) -> ReasoningResult:
        """
        Perform reasoning on market data.
        
        Args:
            df: OHLCV data
            
        Returns:
            ReasoningResult object
        """
        if len(df) < 50:
            return self._get_default_result()
        
        # Check all rules
        applied_rules = []
        evidence = {}
        recommendations = []
        
        for rule_id, rule in self.rules.items():
            if rule.status != 'active':
                continue
            
            # Check condition
            condition_met = self._check_condition(df, rule.condition)
            
            if condition_met:
                applied_rules.append(rule_id)
                evidence[rule_id] = {
                    'condition_met': True,
                    'confidence': rule.confidence,
                    'action': rule.action
                }
                recommendations.append(rule.action)
        
        # Determine conclusion
        if recommendations:
            # Combine recommendations with highest confidence
            best_action = max(recommendations, key=lambda x: x.get('confidence', 0))
            confidence = best_action.get('confidence', 0)
            conclusion = best_action.get('reason', 'No conclusion')
            
            # Weight confidence by number of rules
            confidence = min(confidence * (1 + 0.1 * (len(applied_rules) - 1)), 1.0)
        else:
            conclusion = 'No clear signal'
            confidence = 0.0
        
        result = ReasoningResult(
            timestamp=datetime.now(),
            rules_applied=applied_rules,
            conclusion=conclusion,
            confidence=confidence,
            evidence=evidence,
            recommendation=best_action if recommendations else None
        )
        
        self.results.append(result)
        
        return result
    
    def _check_condition(self, df: pd.DataFrame, condition: Dict[str, Any]) -> bool:
        """
        Check if a condition is met.
        
        Args:
            df: OHLCV data
            condition: Condition dictionary
            
        Returns:
            True if condition is met, False otherwise
        """
        condition_type = condition.get('type')
        
        if condition_type == 'and':
            # Check all sub-conditions
            for sub_condition in condition.get('conditions', []):
                if not self._check_condition(df, sub_condition):
                    return False
            return True
        
        elif condition_type == 'or':
            # Check any sub-condition
            for sub_condition in condition.get('conditions', []):
                if self._check_condition(df, sub_condition):
                    return True
            return False
        
        elif condition_type == 'not':
            # Check if sub-condition is false
            sub_condition = condition.get('condition', {})
            return not self._check_condition(df, sub_condition)
        
        # Simple condition types
        if condition_type == 'price_above_ma':
            ma_period = condition.get('ma_period', 50)
            if len(df) < ma_period:
                return False
            ma = df['close'].rolling(ma_period).mean().iloc[-1]
            return df['close'].iloc[-1] > ma
        
        elif condition_type == 'price_below_ma':
            ma_period = condition.get('ma_period', 50)
            if len(df) < ma_period:
                return False
            ma = df['close'].rolling(ma_period).mean().iloc[-1]
            return df['close'].iloc[-1] < ma
        
        elif condition_type == 'momentum_positive':
            period = condition.get('period', 20)
            if len(df) < period:
                return False
            momentum = (df['close'].iloc[-1] - df['close'].iloc[-period]) / df['close'].iloc[-period]
            return momentum > 0
        
        elif condition_type == 'momentum_negative':
            period = condition.get('period', 20)
            if len(df) < period:
                return False
            momentum = (df['close'].iloc[-1] - df['close'].iloc[-period]) / df['close'].iloc[-period]
            return momentum < 0
        
        elif condition_type == 'rsi_oversold':
            threshold = condition.get('threshold', 30)
            if len(df) < 15:
                return False
            rsi = self._calculate_rsi(df['close'].values)
            return rsi < threshold
        
        elif condition_type == 'rsi_overbought':
            threshold = condition.get('threshold', 70)
            if len(df) < 15:
                return False
            rsi = self._calculate_rsi(df['close'].values)
            return rsi > threshold
        
        elif condition_type == 'price_support':
            lookback = condition.get('lookback', 50)
            if len(df) < lookback:
                return False
            low = df['low'].min()
            return abs(df['close'].iloc[-1] - low) / low < 0.02
        
        elif condition_type == 'price_resistance':
            lookback = condition.get('lookback', 50)
            if len(df) < lookback:
                return False
            high = df['high'].max()
            return abs(df['close'].iloc[-1] - high) / high < 0.02
        
        elif condition_type == 'price_breakout':
            threshold = condition.get('threshold', 0.02)
            if len(df) < 20:
                return False
            high = df['high'].max()
            return (df['close'].iloc[-1] - high) / high > threshold
        
        elif condition_type == 'volume_spike':
            threshold = condition.get('threshold', 1.5)
            if len(df) < 20:
                return False
            avg_volume = df['volume'].mean()
            return df['volume'].iloc[-1] / avg_volume > threshold
        
        return False
    
    def _calculate_rsi(self, close: np.ndarray) -> float:
        """
        Calculate RSI.
        
        Args:
            close: Close prices
            
        Returns:
            RSI value
        """
        if len(close) < 15:
            return 50.0
        
        returns = np.diff(close)
        gains = np.where(returns > 0, returns, 0)
        losses = np.where(returns < 0, -returns, 0)
        
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _get_default_result(self) -> ReasoningResult:
        """
        Get default reasoning result.
        
        Returns:
            Default ReasoningResult object
        """
        return ReasoningResult(
            timestamp=datetime.now(),
            rules_applied=[],
            conclusion='Insufficient data',
            confidence=0.0,
            evidence={},
            recommendation=None
        )
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[ReasoningSignal]:
        """
        Generate trading signal from reasoning.
        
        Args:
            df: OHLCV data
            
        Returns:
            ReasoningSignal or None
        """
        result = self.reason(df)
        
        if result.confidence < self.confidence_threshold:
            return None
        
        if not result.recommendation:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        signal_type = result.recommendation.get('type', 'hold')
        reason = result.conclusion
        
        if signal_type == 'buy':
            target = current_price * 1.02
            stop_loss = current_price * 0.98
        elif signal_type == 'sell':
            target = current_price * 0.98
            stop_loss = current_price * 1.02
        else:
            return None
        
        return ReasoningSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=result.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            reasoning=result,
            indicators={
                'rules_applied': result.rules_applied,
                'evidence': result.evidence
            }
        )
    
    def get_rules_summary(self) -> Dict[str, Any]:
        """
        Get rules summary.
        
        Returns:
            Rules summary
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'total_rules': len(self.rules),
            'active_rules': len([r for r in self.rules.values() if r.status == 'active']),
            'rules': [
                {
                    'id': r.rule_id,
                    'name': r.name,
                    'priority': r.priority,
                    'confidence': r.confidence,
                    'status': r.status
                }
                for r in self.rules.values()
            ],
            'recent_results': self.results[-5:] if self.results else []
        }


def create_reasoning_model(config: Optional[Dict[str, Any]] = None) -> ReasoningModel:
    """
    Create a reasoning model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ReasoningModel instance
    """
    return ReasoningModel(config)


__all__ = [
    'ReasoningRule',
    'ReasoningResult',
    'ReasoningSignal',
    'ReasoningModel',
    'create_reasoning_model'
]
