"""
Swing Bot Feedback Model
==========================

This module provides feedback analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class FeedbackMetrics:
    """Feedback metrics data structure."""
    timestamp: datetime
    positive_feedback: float
    negative_feedback: float
    net_feedback: float
    feedback_ratio: float
    feedback_velocity: float
    sentiment_score: float
    confidence_score: float
    learning_rate: float


@dataclass
class FeedbackSignal:
    """Feedback trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: FeedbackMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class FeedbackModel:
    """
    Feedback analysis model for market sentiment and behavior.
    
    Implements feedback analysis for trading decisions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the feedback model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[FeedbackMetrics] = []
        
        # Feedback history
        self.feedback_history: List[float] = []
        self.positive_count = 0
        self.negative_count = 0
        
    def analyze(self, df: pd.DataFrame, feedback_data: List[float]) -> Dict[str, Any]:
        """
        Analyze feedback metrics.
        
        Args:
            df: OHLCV data
            feedback_data: List of feedback values
            
        Returns:
            Feedback analysis results
        """
        if len(df) < self.lookback_period or not feedback_data:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate metrics
        metrics = self._calculate_metrics(df, feedback_data)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(df, metrics)
        }
    
    def _calculate_metrics(self, df: pd.DataFrame, feedback_data: List[float]) -> FeedbackMetrics:
        """
        Calculate feedback metrics.
        
        Args:
            df: OHLCV data
            feedback_data: List of feedback values
            
        Returns:
            FeedbackMetrics object
        """
        # Update feedback history
        self.feedback_history.extend(feedback_data)
        
        # Keep only recent history
        if len(self.feedback_history) > self.lookback_period:
            self.feedback_history = self.feedback_history[-self.lookback_period:]
        
        # Calculate positive and negative feedback
        positive_feedback = sum(1 for f in feedback_data if f > 0)
        negative_feedback = sum(1 for f in feedback_data if f < 0)
        total_feedback = len(feedback_data)
        
        # Update counts
        self.positive_count += positive_feedback
        self.negative_count += negative_feedback
        
        # Calculate metrics
        if total_feedback > 0:
            positive_ratio = positive_feedback / total_feedback
            negative_ratio = negative_feedback / total_feedback
            net_feedback = (positive_feedback - negative_feedback) / total_feedback
            feedback_ratio = positive_feedback / (negative_feedback + 1e-10)
        else:
            positive_ratio = 0.5
            negative_ratio = 0.5
            net_feedback = 0.0
            feedback_ratio = 1.0
        
        # Calculate feedback velocity
        if len(self.feedback_history) > 1:
            feedback_velocity = self.feedback_history[-1] - self.feedback_history[-2]
        else:
            feedback_velocity = 0.0
        
        # Calculate sentiment score
        sentiment_score = (positive_ratio - negative_ratio)
        
        # Calculate confidence score
        total_feedback_count = self.positive_count + self.negative_count
        if total_feedback_count > 0:
            confidence_score = max(self.positive_count, self.negative_count) / total_feedback_count
        else:
            confidence_score = 0.5
        
        # Calculate learning rate
        if len(self.feedback_history) > 5:
            learning_rate = np.std(self.feedback_history[-10:])
        else:
            learning_rate = 0.0
        
        metrics = FeedbackMetrics(
            timestamp=datetime.now(),
            positive_feedback=positive_ratio,
            negative_feedback=negative_ratio,
            net_feedback=net_feedback,
            feedback_ratio=feedback_ratio,
            feedback_velocity=feedback_velocity,
            sentiment_score=sentiment_score,
            confidence_score=confidence_score,
            learning_rate=learning_rate
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _get_default_metrics(self) -> FeedbackMetrics:
        """
        Get default metrics.
        
        Returns:
            Default FeedbackMetrics object
        """
        return FeedbackMetrics(
            timestamp=datetime.now(),
            positive_feedback=0.5,
            negative_feedback=0.5,
            net_feedback=0.0,
            feedback_ratio=1.0,
            feedback_velocity=0.0,
            sentiment_score=0.0,
            confidence_score=0.5,
            learning_rate=0.0
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: FeedbackMetrics) -> List[FeedbackSignal]:
        """
        Generate trading signals from feedback metrics.
        
        Args:
            df: OHLCV data
            metrics: FeedbackMetrics object
            
        Returns:
            List of FeedbackSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check sentiment and confidence
        if abs(metrics.sentiment_score) < self.confidence_threshold:
            return signals
        
        # Generate signal based on sentiment
        if metrics.sentiment_score > 0.3:
            signal_type = 'buy'
            reason = f"Positive feedback sentiment ({metrics.sentiment_score:.2f})"
            confidence = metrics.confidence_score
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif metrics.sentiment_score < -0.3:
            signal_type = 'sell'
            reason = f"Negative feedback sentiment ({metrics.sentiment_score:.2f})"
            confidence = metrics.confidence_score
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(FeedbackSignal(
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
                'sentiment': metrics.sentiment_score,
                'feedback_ratio': metrics.feedback_ratio,
                'confidence': metrics.confidence_score,
                'velocity': metrics.feedback_velocity
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: FeedbackMetrics) -> str:
        """
        Get status from feedback metrics.
        
        Args:
            metrics: FeedbackMetrics object
            
        Returns:
            Status string
        """
        if metrics.sentiment_score > 0.3:
            return 'positive'
        elif metrics.sentiment_score > 0.1:
            return 'slightly_positive'
        elif metrics.sentiment_score > -0.1:
            return 'neutral'
        elif metrics.sentiment_score > -0.3:
            return 'slightly_negative'
        else:
            return 'negative'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: FeedbackMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: FeedbackMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'positive': f"Positive sentiment ({metrics.sentiment_score:.2f})",
            'slightly_positive': f"Slightly positive sentiment ({metrics.sentiment_score:.2f})",
            'neutral': f"Neutral sentiment ({metrics.sentiment_score:.2f})",
            'slightly_negative': f"Slightly negative sentiment ({metrics.sentiment_score:.2f})",
            'negative': f"Negative sentiment ({metrics.sentiment_score:.2f})"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get feedback metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_sentiment': np.mean([m.sentiment_score for m in self.metrics_history]),
            'average_confidence': np.mean([m.confidence_score for m in self.metrics_history]),
            'average_feedback_ratio': np.mean([m.feedback_ratio for m in self.metrics_history]),
            'total_feedback': len(self.feedback_history),
            'positive_percentage': (self.positive_count / (self.positive_count + self.negative_count) * 100) if (self.positive_count + self.negative_count) > 0 else 0,
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_feedback_model(config: Optional[Dict[str, Any]] = None) -> FeedbackModel:
    """
    Create a feedback model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        FeedbackModel instance
    """
    return FeedbackModel(config)


__all__ = [
    'FeedbackMetrics',
    'FeedbackSignal',
    'FeedbackModel',
    'create_feedback_model'
]
