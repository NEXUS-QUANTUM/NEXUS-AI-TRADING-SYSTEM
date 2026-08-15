"""
Swing Bot Macro Model
=======================

This module provides macroeconomic analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class MacroIndicator:
    """Macroeconomic indicator data structure."""
    name: str
    value: float
    previous_value: float
    change: float
    expected_value: float
    surprise: float
    impact: str  # 'positive', 'negative', 'neutral'
    timestamp: datetime


@dataclass
class MacroSignal:
    """Macroeconomic trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    indicators: List[MacroIndicator]
    composite_score: float


class MacroModel:
    """
    Macroeconomic analysis model for market context.
    
    Implements macro analysis for trading decisions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the macro model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.indicators: Dict[str, MacroIndicator] = {}
        self.history: List[Dict[str, Any]] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Define macro indicators
        self.macro_categories = {
            'growth': ['gdp', 'industrial_production', 'retail_sales'],
            'employment': ['unemployment', 'nonfarm_payrolls', 'jobless_claims'],
            'inflation': ['cpi', 'ppi', 'pce'],
            'monetary': ['fed_funds_rate', 'money_supply', 'reserve_balance'],
            'trade': ['trade_balance', 'current_account', 'import_export'],
            'sentiment': ['consumer_confidence', 'business_sentiment', 'pmi']
        }
        
        # Weighting for each category
        self.category_weights = {
            'growth': 0.25,
            'employment': 0.15,
            'inflation': 0.20,
            'monetary': 0.20,
            'trade': 0.10,
            'sentiment': 0.10
        }
        
    def update_indicator(self, name: str, value: float, expected_value: Optional[float] = None) -> None:
        """
        Update a macroeconomic indicator.
        
        Args:
            name: Indicator name
            value: Current value
            expected_value: Expected value
        """
        previous_value = self.indicators[name].value if name in self.indicators else value
        
        change = (value - previous_value) / previous_value if previous_value != 0 else 0
        surprise = (value - expected_value) / expected_value if expected_value and expected_value != 0 else 0
        
        # Determine impact
        impact = self._determine_impact(name, value, expected_value)
        
        indicator = MacroIndicator(
            name=name,
            value=value,
            previous_value=previous_value,
            change=change,
            expected_value=expected_value or value,
            surprise=surprise,
            impact=impact,
            timestamp=datetime.now()
        )
        
        self.indicators[name] = indicator
        
        # Add to history
        self.history.append({
            'timestamp': datetime.now(),
            'name': name,
            'value': value,
            'change': change,
            'surprise': surprise
        })
    
    def _determine_impact(self, name: str, value: float, expected_value: Optional[float]) -> str:
        """
        Determine the impact of an indicator.
        
        Args:
            name: Indicator name
            value: Current value
            expected_value: Expected value
            
        Returns:
            Impact string
        """
        if expected_value is None:
            return 'neutral'
        
        # For most indicators, higher than expected is positive
        positive_indicators = ['gdp', 'industrial_production', 'retail_sales', 
                              'nonfarm_payrolls', 'consumer_confidence', 
                              'business_sentiment', 'pmi']
        
        negative_indicators = ['unemployment', 'jobless_claims', 'cpi', 'ppi', 
                              'pce', 'fed_funds_rate']
        
        diff = (value - expected_value) / expected_value if expected_value != 0 else 0
        
        if abs(diff) < 0.01:
            return 'neutral'
        
        if name in positive_indicators:
            return 'positive' if diff > 0 else 'negative'
        elif name in negative_indicators:
            return 'negative' if diff > 0 else 'positive'
        else:
            return 'neutral'
    
    def analyze(self) -> Dict[str, Any]:
        """
        Analyze macroeconomic conditions.
        
        Returns:
            Macro analysis results
        """
        if not self.indicators:
            return {'status': 'insufficient_data', 'signal': None}
        
        # Calculate category scores
        category_scores = {}
        category_details = {}
        
        for category, indicators in self.macro_categories.items():
            scores = []
            for indicator_name in indicators:
                if indicator_name in self.indicators:
                    indicator = self.indicators[indicator_name]
                    # Convert impact to score
                    if indicator.impact == 'positive':
                        score = 1.0
                    elif indicator.impact == 'negative':
                        score = -1.0
                    else:
                        score = 0.0
                    scores.append(score)
            
            if scores:
                category_score = np.mean(scores)
                category_scores[category] = category_score
                category_details[category] = {
                    'score': category_score,
                    'indicators': {name: self.indicators[name].impact for name in indicators if name in self.indicators}
                }
        
        # Calculate composite score
        composite_score = 0
        for category, score in category_scores.items():
            composite_score += score * self.category_weights.get(category, 1/len(category_scores))
        
        # Determine overall sentiment
        sentiment = 'neutral'
        if composite_score > 0.3:
            sentiment = 'bullish'
        elif composite_score < -0.3:
            sentiment = 'bearish'
        
        # Generate signal
        signal = self._generate_signal(composite_score, category_scores)
        
        return {
            'composite_score': composite_score,
            'category_scores': category_scores,
            'category_details': category_details,
            'sentiment': sentiment,
            'signal': signal,
            'timestamp': datetime.now()
        }
    
    def _generate_signal(self, composite_score: float, category_scores: Dict[str, float]) -> Optional[MacroSignal]:
        """
        Generate trading signal from macro analysis.
        
        Args:
            composite_score: Composite macro score
            category_scores: Category scores
            
        Returns:
            MacroSignal or None
        """
        if abs(composite_score) < self.confidence_threshold:
            return None
        
        # Get current price (placeholder)
        current_price = 100.0
        
        if composite_score > 0.3:
            signal_type = 'buy'
            reason = f"Positive macro conditions (score: {composite_score:.2f})"
            confidence = min(abs(composite_score), 1.0)
            target = current_price * 1.05
            stop_loss = current_price * 0.95
            
        elif composite_score < -0.3:
            signal_type = 'sell'
            reason = f"Negative macro conditions (score: {composite_score:.2f})"
            confidence = min(abs(composite_score), 1.0)
            target = current_price * 0.95
            stop_loss = current_price * 1.05
            
        else:
            return None
        
        return MacroSignal(
            symbol='MACRO',
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            indicators=list(self.indicators.values()),
            composite_score=composite_score
        )
    
    def get_macro_summary(self) -> Dict[str, Any]:
        """
        Get macro summary.
        
        Returns:
            Macro summary
        """
        analysis = self.analyze()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'composite_score': analysis.get('composite_score', 0),
            'sentiment': analysis.get('sentiment', 'neutral'),
            'category_scores': analysis.get('category_scores', {}),
            'indicator_count': len(self.indicators),
            'history_length': len(self.history),
            'latest_indicators': [
                {
                    'name': name,
                    'value': ind.value,
                    'impact': ind.impact,
                    'surprise': ind.surprise
                }
                for name, ind in self.indicators.items()
            ][-10:]
        }


def create_macro_model(config: Optional[Dict[str, Any]] = None) -> MacroModel:
    """
    Create a macro model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        MacroModel instance
    """
    return MacroModel(config)


__all__ = [
    'MacroIndicator',
    'MacroSignal',
    'MacroModel',
    'create_macro_model'
]
