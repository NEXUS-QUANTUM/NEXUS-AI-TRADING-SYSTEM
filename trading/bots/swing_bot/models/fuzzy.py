"""
Swing Bot Fuzzy Model
=======================

This module provides fuzzy logic models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
import warnings
warnings.filterwarnings('ignore')


@dataclass
class FuzzyMembership:
    """Fuzzy membership data structure."""
    name: str
    value: float
    membership: Dict[str, float]  # linguistic term -> membership degree


@dataclass
class FuzzyRule:
    """Fuzzy rule data structure."""
    antecedents: Dict[str, str]  # variable -> linguistic term
    consequent: Dict[str, str]  # variable -> linguistic term
    weight: float
    confidence: float


@dataclass
class FuzzyResult:
    """Fuzzy inference result."""
    timestamp: datetime
    inputs: Dict[str, float]
    outputs: Dict[str, float]
    fired_rules: List[FuzzyRule]
    confidence: float


@dataclass
class FuzzySignal:
    """Fuzzy trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    result: FuzzyResult
    indicators: Dict[str, Any] = field(default_factory=dict)


class FuzzyModel:
    """
    Fuzzy logic model for trading decisions.
    
    Implements fuzzy inference systems for market analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the fuzzy model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.linguistic_variables: Dict[str, Dict[str, Any]] = {}
        self.rules: List[FuzzyRule] = []
        self.results: List[FuzzyResult] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Initialize fuzzy system
        self._initialize_fuzzy_system()
        
    def _initialize_fuzzy_system(self) -> None:
        """Initialize the fuzzy inference system."""
        # Define linguistic variables
        self.linguistic_variables = {
            'momentum': {
                'low': {'type': 'trapezoid', 'params': [-1, -0.5, -0.2, 0]},
                'neutral': {'type': 'triangle', 'params': [-0.2, 0, 0.2]},
                'high': {'type': 'trapezoid', 'params': [0, 0.2, 0.5, 1]}
            },
            'rsi': {
                'low': {'type': 'trapezoid', 'params': [0, 20, 30, 40]},
                'medium': {'type': 'triangle', 'params': [30, 50, 70]},
                'high': {'type': 'trapezoid', 'params': [60, 70, 80, 100]}
            },
            'volatility': {
                'low': {'type': 'trapezoid', 'params': [0, 0.05, 0.1, 0.15]},
                'medium': {'type': 'triangle', 'params': [0.1, 0.2, 0.3]},
                'high': {'type': 'trapezoid', 'params': [0.2, 0.3, 0.4, 0.5]}
            },
            'trend': {
                'down': {'type': 'trapezoid', 'params': [-1, -0.5, -0.2, 0]},
                'neutral': {'type': 'triangle', 'params': [-0.2, 0, 0.2]},
                'up': {'type': 'trapezoid', 'params': [0, 0.2, 0.5, 1]}
            },
            'signal': {
                'sell': {'type': 'trapezoid', 'params': [-1, -0.5, -0.2, 0]},
                'hold': {'type': 'triangle', 'params': [-0.2, 0, 0.2]},
                'buy': {'type': 'trapezoid', 'params': [0, 0.2, 0.5, 1]}
            }
        }
        
        # Define fuzzy rules
        self.rules = [
            # Strong buy rules
            FuzzyRule(
                antecedents={'momentum': 'high', 'rsi': 'low', 'trend': 'up'},
                consequent={'signal': 'buy'},
                weight=0.9,
                confidence=0.8
            ),
            FuzzyRule(
                antecedents={'momentum': 'high', 'rsi': 'low', 'volatility': 'low'},
                consequent={'signal': 'buy'},
                weight=0.8,
                confidence=0.7
            ),
            # Strong sell rules
            FuzzyRule(
                antecedents={'momentum': 'low', 'rsi': 'high', 'trend': 'down'},
                consequent={'signal': 'sell'},
                weight=0.9,
                confidence=0.8
            ),
            FuzzyRule(
                antecedents={'momentum': 'low', 'rsi': 'high', 'volatility': 'high'},
                consequent={'signal': 'sell'},
                weight=0.8,
                confidence=0.7
            ),
            # Moderate rules
            FuzzyRule(
                antecedents={'momentum': 'neutral', 'rsi': 'low', 'trend': 'up'},
                consequent={'signal': 'buy'},
                weight=0.6,
                confidence=0.6
            ),
            FuzzyRule(
                antecedents={'momentum': 'neutral', 'rsi': 'high', 'trend': 'down'},
                consequent={'signal': 'sell'},
                weight=0.6,
                confidence=0.6
            ),
            # Hold rules
            FuzzyRule(
                antecedents={'momentum': 'neutral', 'rsi': 'medium', 'trend': 'neutral'},
                consequent={'signal': 'hold'},
                weight=0.5,
                confidence=0.5
            ),
            FuzzyRule(
                antecedents={'momentum': 'neutral', 'rsi': 'medium', 'volatility': 'medium'},
                consequent={'signal': 'hold'},
                weight=0.5,
                confidence=0.5
            )
        ]
    
    def _calculate_membership(self, value: float, term: str, params: List[float]) -> float:
        """
        Calculate membership degree for a fuzzy term.
        
        Args:
            value: Input value
            term: Fuzzy term
            params: Term parameters
            
        Returns:
            Membership degree (0-1)
        """
        if term == 'trapezoid':
            a, b, c, d = params
            if value <= a or value >= d:
                return 0.0
            elif value <= b:
                return (value - a) / (b - a) if b != a else 1.0
            elif value <= c:
                return 1.0
            else:
                return (d - value) / (d - c) if d != c else 1.0
        
        elif term == 'triangle':
            a, b, c = params
            if value <= a or value >= c:
                return 0.0
            elif value <= b:
                return (value - a) / (b - a) if b != a else 1.0
            else:
                return (c - value) / (c - b) if c != b else 1.0
        
        return 0.0
    
    def _fuzzify(self, inputs: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        """
        Fuzzify input variables.
        
        Args:
            inputs: Input values
            
        Returns:
            Fuzzified values
        """
        fuzzified = {}
        
        for var_name, value in inputs.items():
            if var_name in self.linguistic_variables:
                fuzzified[var_name] = {}
                for term_name, term_data in self.linguistic_variables[var_name].items():
                    membership = self._calculate_membership(
                        value,
                        term_data['type'],
                        term_data['params']
                    )
                    fuzzified[var_name][term_name] = membership
        
        return fuzzified
    
    def _evaluate_rules(self, fuzzified: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """
        Evaluate fuzzy rules.
        
        Args:
            fuzzified: Fuzzified input values
            
        Returns:
            List of rule evaluation results
        """
        results = []
        
        for rule in self.rules:
            # Calculate rule strength (min of antecedent memberships)
            strengths = []
            for var, term in rule.antecedents.items():
                if var in fuzzified and term in fuzzified[var]:
                    strengths.append(fuzzified[var][term])
                else:
                    strengths.append(0.0)
            
            if strengths:
                rule_strength = min(strengths) * rule.weight
                results.append({
                    'rule': rule,
                    'strength': rule_strength,
                    'output': rule.consequent
                })
        
        return results
    
    def _defuzzify(self, rule_results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Defuzzify to crisp outputs.
        
        Args:
            rule_results: Rule evaluation results
            
        Returns:
            Defuzzified outputs
        """
        outputs = {}
        
        # Use centroid defuzzification
        for result in rule_results:
            output_var = list(result['output'].keys())[0]
            output_term = result['output'][output_var]
            strength = result['strength']
            
            if output_var not in outputs:
                outputs[output_var] = []
            
            # Get centroid of output term
            if output_var in self.linguistic_variables:
                term_data = self.linguistic_variables[output_var][output_term]
                params = term_data['params']
                
                # Calculate centroid
                if term_data['type'] == 'trapezoid':
                    a, b, c, d = params
                    centroid = (a + b + c + d) / 4
                elif term_data['type'] == 'triangle':
                    a, b, c = params
                    centroid = (a + b + c) / 3
                else:
                    centroid = np.mean(params)
                
                outputs[output_var].append((centroid, strength))
        
        # Weighted average
        defuzzified = {}
        for var, items in outputs.items():
            total_weight = sum(s for _, s in items)
            if total_weight > 0:
                value = sum(c * s for c, s in items) / total_weight
                defuzzified[var] = value
            else:
                defuzzified[var] = 0.0
        
        return defuzzified
    
    def infer(self, inputs: Dict[str, float]) -> FuzzyResult:
        """
        Perform fuzzy inference.
        
        Args:
            inputs: Input values
            
        Returns:
            FuzzyResult object
        """
        # Fuzzify inputs
        fuzzified = self._fuzzify(inputs)
        
        # Evaluate rules
        rule_results = self._evaluate_rules(fuzzified)
        
        # Defuzzify
        outputs = self._defuzzify(rule_results)
        
        # Calculate confidence
        total_strength = sum(r['strength'] for r in rule_results)
        max_strength = max(r['strength'] for r in rule_results) if rule_results else 0
        confidence = min(max_strength, 1.0)
        
        # Get fired rules
        fired_rules = [r['rule'] for r in rule_results if r['strength'] > 0.1]
        
        result = FuzzyResult(
            timestamp=datetime.now(),
            inputs=inputs,
            outputs=outputs,
            fired_rules=fired_rules,
            confidence=confidence
        )
        
        self.results.append(result)
        
        return result
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[FuzzySignal]:
        """
        Generate trading signal from fuzzy inference.
        
        Args:
            df: OHLCV data
            
        Returns:
            FuzzySignal or None
        """
        if len(df) < 20:
            return None
        
        # Calculate input values
        close = df['close'].values
        returns = np.diff(np.log(close))
        
        momentum = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0
        rsi = self._calculate_rsi(close)
        volatility = np.std(returns[-20:]) * np.sqrt(252) if len(returns) >= 20 else 0
        trend = (close[-1] - close[-10]) / close[-10] if len(close) >= 10 else 0
        
        inputs = {
            'momentum': momentum,
            'rsi': rsi,
            'volatility': volatility,
            'trend': trend
        }
        
        # Perform inference
        result = self.infer(inputs)
        
        if result.confidence < self.confidence_threshold:
            return None
        
        current_price = close[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal based on output
        output_signal = result.outputs.get('signal', 0)
        
        if output_signal > 0.3:
            signal_type = 'buy'
            reason = "Fuzzy logic indicates buying opportunity"
            confidence = result.confidence
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif output_signal < -0.3:
            signal_type = 'sell'
            reason = "Fuzzy logic indicates selling opportunity"
            confidence = result.confidence
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return None
        
        return FuzzySignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            result=result,
            indicators={
                'inputs': inputs,
                'fired_rules': len(result.fired_rules),
                'confidence': result.confidence
            }
        )
    
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
    
    def get_fuzzy_summary(self) -> Dict[str, Any]:
        """
        Get fuzzy inference summary.
        
        Returns:
            Fuzzy summary
        """
        if not self.results:
            return {'status': 'no_results'}
        
        latest = self.results[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_result': latest,
            'total_inferences': len(self.results),
            'average_confidence': np.mean([r.confidence for r in self.results]),
            'rules_fired': len(self.rules),
            'linguistic_variables': list(self.linguistic_variables.keys()),
            'latest_output': latest.outputs
        }


def create_fuzzy_model(config: Optional[Dict[str, Any]] = None) -> FuzzyModel:
    """
    Create a fuzzy model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        FuzzyModel instance
    """
    return FuzzyModel(config)


__all__ = [
    'FuzzyMembership',
    'FuzzyRule',
    'FuzzyResult',
    'FuzzySignal',
    'FuzzyModel',
    'create_fuzzy_model'
]
