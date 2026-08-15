"""
Swing Bot Intelligence Model
==============================

This module provides intelligence and cognitive models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class IntelligenceMetrics:
    """Intelligence metrics data structure."""
    timestamp: datetime
    cognitive_score: float
    learning_rate: float
    adaptation_score: float
    pattern_recognition: float
    decision_quality: float
    knowledge_retention: float
    reasoning_ability: float
    creativity_score: float


@dataclass
class IntelligenceSignal:
    """Intelligence trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: IntelligenceMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class IntelligenceModel:
    """
    Intelligence analysis model for cognitive trading.
    
    Implements cognitive metrics for trading decisions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the intelligence model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[IntelligenceMetrics] = []
        self.knowledge_base: Dict[str, Any] = {}
        self.learning_history: List[Dict[str, Any]] = []
        
    def analyze(self, df: pd.DataFrame, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze intelligence metrics.
        
        Args:
            df: OHLCV data
            market_data: Additional market data
            
        Returns:
            Intelligence analysis results
        """
        if len(df) < self.lookback_period:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate metrics
        metrics = self._calculate_metrics(df, market_data)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(df, metrics)
        }
    
    def _calculate_metrics(self, df: pd.DataFrame, market_data: Dict[str, Any]) -> IntelligenceMetrics:
        """
        Calculate intelligence metrics.
        
        Args:
            df: OHLCV data
            market_data: Additional market data
            
        Returns:
            IntelligenceMetrics object
        """
        close = df['close'].values
        
        # Calculate cognitive score
        cognitive_score = self._calculate_cognitive_score(df, market_data)
        
        # Calculate learning rate
        learning_rate = self._calculate_learning_rate(df)
        
        # Calculate adaptation score
        adaptation_score = self._calculate_adaptation_score(df)
        
        # Calculate pattern recognition
        pattern_recognition = self._calculate_pattern_recognition(df)
        
        # Calculate decision quality
        decision_quality = self._calculate_decision_quality(df)
        
        # Calculate knowledge retention
        knowledge_retention = self._calculate_knowledge_retention(df)
        
        # Calculate reasoning ability
        reasoning_ability = self._calculate_reasoning_ability(df)
        
        # Calculate creativity score
        creativity_score = self._calculate_creativity_score(df)
        
        metrics = IntelligenceMetrics(
            timestamp=datetime.now(),
            cognitive_score=cognitive_score,
            learning_rate=learning_rate,
            adaptation_score=adaptation_score,
            pattern_recognition=pattern_recognition,
            decision_quality=decision_quality,
            knowledge_retention=knowledge_retention,
            reasoning_ability=reasoning_ability,
            creativity_score=creativity_score
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_cognitive_score(self, df: pd.DataFrame, market_data: Dict[str, Any]) -> float:
        """
        Calculate cognitive score.
        
        Args:
            df: OHLCV data
            market_data: Additional market data
            
        Returns:
            Cognitive score (0-1)
        """
        # Combine multiple cognitive factors
        factors = [
            self._calculate_pattern_recognition(df),
            self._calculate_decision_quality(df),
            self._calculate_reasoning_ability(df)
        ]
        
        return np.mean(factors)
    
    def _calculate_learning_rate(self, df: pd.DataFrame) -> float:
        """
        Calculate learning rate.
        
        Args:
            df: OHLCV data
            
        Returns:
            Learning rate (0-1)
        """
        close = df['close'].values
        
        if len(close) < 20:
            return 0.5
        
        # Calculate how quickly patterns are learned
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-20:]) * np.sqrt(252)
        
        # Learning rate inversely related to volatility
        learning_rate = 1 / (1 + volatility)
        
        return max(0, min(1, learning_rate))
    
    def _calculate_adaptation_score(self, df: pd.DataFrame) -> float:
        """
        Calculate adaptation score.
        
        Args:
            df: OHLCV data
            
        Returns:
            Adaptation score (0-1)
        """
        close = df['close'].values
        
        if len(close) < 20:
            return 0.5
        
        # Calculate how quickly price adapts to new levels
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-20:]) * np.sqrt(252)
        
        # Adaptation score based on volatility change
        if len(returns) >= 40:
            vol_old = np.std(returns[-40:-20]) * np.sqrt(252)
            vol_change = abs(volatility - vol_old) / (vol_old + 1e-10)
            adaptation = 1 / (1 + vol_change)
        else:
            adaptation = 0.5
        
        return max(0, min(1, adaptation))
    
    def _calculate_pattern_recognition(self, df: pd.DataFrame) -> float:
        """
        Calculate pattern recognition score.
        
        Args:
            df: OHLCV data
            
        Returns:
            Pattern recognition score (0-1)
        """
        close = df['close'].values
        
        if len(close) < 30:
            return 0.5
        
        # Detect simple patterns
        patterns_found = 0
        total_patterns = 0
        
        # Check for support/resistance patterns
        for i in range(1, len(close)-1):
            if (close[i] > close[i-1] and close[i] > close[i+1]):
                patterns_found += 1
            elif (close[i] < close[i-1] and close[i] < close[i+1]):
                patterns_found += 1
            total_patterns += 1
        
        if total_patterns == 0:
            return 0.5
        
        pattern_score = patterns_found / total_patterns
        
        return max(0, min(1, pattern_score))
    
    def _calculate_decision_quality(self, df: pd.DataFrame) -> float:
        """
        Calculate decision quality score.
        
        Args:
            df: OHLCV data
            
        Returns:
            Decision quality score (0-1)
        """
        close = df['close'].values
        
        if len(close) < 20:
            return 0.5
        
        # Calculate trend strength
        slope, intercept = MathUtils.linear_regression(
            np.arange(20),
            close[-20:]
        )
        r2 = MathUtils.r_squared(np.arange(20), close[-20:])
        
        # Decision quality based on trend strength and reliability
        trend_strength = min(abs(slope) * 10, 1.0)
        quality = (trend_strength + r2) / 2
        
        return max(0, min(1, quality))
    
    def _calculate_knowledge_retention(self, df: pd.DataFrame) -> float:
        """
        Calculate knowledge retention score.
        
        Args:
            df: OHLCV data
            
        Returns:
            Knowledge retention score (0-1)
        """
        close = df['close'].values
        
        if len(close) < 50:
            return 0.5
        
        # Calculate autocorrelation as measure of memory
        returns = np.diff(np.log(close))
        autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        
        # Knowledge retention based on autocorrelation
        retention = (autocorr + 1) / 2
        
        return max(0, min(1, retention))
    
    def _calculate_reasoning_ability(self, df: pd.DataFrame) -> float:
        """
        Calculate reasoning ability score.
        
        Args:
            df: OHLCV data
            
        Returns:
            Reasoning ability score (0-1)
        """
        close = df['close'].values
        
        if len(close) < 20:
            return 0.5
        
        # Calculate complexity of price movements
        returns = np.diff(np.log(close))
        entropy = self._calculate_entropy(returns)
        
        # Reasoning ability based on entropy
        reasoning = 1 - entropy
        
        return max(0, min(1, reasoning))
    
    def _calculate_creativity_score(self, df: pd.DataFrame) -> float:
        """
        Calculate creativity score.
        
        Args:
            df: OHLCV data
            
        Returns:
            Creativity score (0-1)
        """
        close = df['close'].values
        
        if len(close) < 20:
            return 0.5
        
        # Calculate novelty of price movements
        returns = np.diff(np.log(close))
        
        # Check for unusual patterns
        creativity = 0
        for i in range(len(returns) - 1):
            if abs(returns[i]) > 2 * np.std(returns):
                creativity += 1
        
        creativity = creativity / len(returns) if len(returns) > 0 else 0
        
        return max(0, min(1, creativity))
    
    def _calculate_entropy(self, data: np.ndarray) -> float:
        """
        Calculate entropy of data.
        
        Args:
            data: Input data
            
        Returns:
            Entropy (0-1)
        """
        if len(data) < 10:
            return 0.5
        
        hist, _ = np.histogram(data, bins=10)
        hist = hist / len(data)
        entropy = -np.sum(hist * np.log(hist + 1e-10))
        max_entropy = np.log(10)
        
        return entropy / max_entropy if max_entropy > 0 else 0
    
    def _get_default_metrics(self) -> IntelligenceMetrics:
        """
        Get default metrics.
        
        Returns:
            Default IntelligenceMetrics object
        """
        return IntelligenceMetrics(
            timestamp=datetime.now(),
            cognitive_score=0.5,
            learning_rate=0.5,
            adaptation_score=0.5,
            pattern_recognition=0.5,
            decision_quality=0.5,
            knowledge_retention=0.5,
            reasoning_ability=0.5,
            creativity_score=0.5
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: IntelligenceMetrics) -> List[IntelligenceSignal]:
        """
        Generate trading signals from intelligence metrics.
        
        Args:
            df: OHLCV data
            metrics: IntelligenceMetrics object
            
        Returns:
            List of IntelligenceSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check cognitive score
        if metrics.cognitive_score < self.confidence_threshold:
            return signals
        
        # Generate signal based on cognitive metrics
        if metrics.decision_quality > 0.7 and metrics.pattern_recognition > 0.6:
            signal_type = 'buy'
            reason = "High decision quality and pattern recognition"
            confidence = metrics.cognitive_score
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif metrics.decision_quality < 0.4 and metrics.learning_rate > 0.3:
            signal_type = 'sell'
            reason = "Low decision quality with active learning"
            confidence = 1 - metrics.cognitive_score
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(IntelligenceSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            metrics=metrics,
            indicators={
                'cognitive_score': metrics.cognitive_score,
                'learning_rate': metrics.learning_rate,
                'adaptation': metrics.adaptation_score,
                'reasoning': metrics.reasoning_ability
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: IntelligenceMetrics) -> str:
        """
        Get status from intelligence metrics.
        
        Args:
            metrics: IntelligenceMetrics object
            
        Returns:
            Status string
        """
        if metrics.cognitive_score > 0.7:
            return 'high_intelligence'
        elif metrics.cognitive_score > 0.5:
            return 'moderate_intelligence'
        else:
            return 'low_intelligence'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: IntelligenceMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: IntelligenceMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'high_intelligence': "High cognitive capacity - strong patterns",
            'moderate_intelligence': "Moderate cognitive capacity",
            'low_intelligence': "Low cognitive capacity - uncertain market"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get intelligence metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_cognitive': np.mean([m.cognitive_score for m in self.metrics_history]),
            'average_learning': np.mean([m.learning_rate for m in self.metrics_history]),
            'average_adaptation': np.mean([m.adaptation_score for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_intelligence_model(config: Optional[Dict[str, Any]] = None) -> IntelligenceModel:
    """
    Create an intelligence model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        IntelligenceModel instance
    """
    return IntelligenceModel(config)


__all__ = [
    'IntelligenceMetrics',
    'IntelligenceSignal',
    'IntelligenceModel',
    'create_intelligence_model'
]
