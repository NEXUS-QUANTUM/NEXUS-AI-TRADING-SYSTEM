"""
Swing Bot Learning Model
==========================

This module provides learning and adaptation models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
import warnings
warnings.filterwarnings('ignore')


@dataclass
class LearningMetrics:
    """Learning metrics data structure."""
    timestamp: datetime
    learning_rate: float
    knowledge_retention: float
    adaptation_speed: float
    prediction_accuracy: float
    error_rate: float
    confidence_growth: float
    model_stability: float


@dataclass
class LearningSignal:
    """Learning trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: LearningMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class LearningModel:
    """
    Learning and adaptation model for trading improvement.
    
    Implements learning metrics and adaptation strategies.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the learning model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[LearningMetrics] = []
        self.prediction_history: List[float] = []
        self.error_history: List[float] = []
        
    def analyze(self, df: pd.DataFrame, predictions: List[float]) -> Dict[str, Any]:
        """
        Analyze learning metrics.
        
        Args:
            df: OHLCV data
            predictions: List of predictions
            
        Returns:
            Learning analysis results
        """
        if len(df) < self.lookback_period:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Update prediction history
        if predictions:
            self.prediction_history.extend(predictions)
            if len(self.prediction_history) > self.lookback_period:
                self.prediction_history = self.prediction_history[-self.lookback_period:]
        
        # Calculate metrics
        metrics = self._calculate_metrics(df)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(df, metrics)
        }
    
    def _calculate_metrics(self, df: pd.DataFrame) -> LearningMetrics:
        """
        Calculate learning metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            LearningMetrics object
        """
        close = df['close'].values
        actual_values = close[-len(self.prediction_history):] if self.prediction_history else close[-10:]
        
        # Calculate learning rate
        learning_rate = self._calculate_learning_rate(df)
        
        # Calculate knowledge retention
        retention = self._calculate_knowledge_retention(df)
        
        # Calculate adaptation speed
        adaptation = self._calculate_adaptation_speed(df)
        
        # Calculate prediction accuracy
        accuracy = self._calculate_prediction_accuracy(actual_values, self.prediction_history)
        
        # Calculate error rate
        error_rate = self._calculate_error_rate(actual_values, self.prediction_history)
        
        # Calculate confidence growth
        confidence_growth = self._calculate_confidence_growth(df)
        
        # Calculate model stability
        stability = self._calculate_model_stability(df)
        
        metrics = LearningMetrics(
            timestamp=datetime.now(),
            learning_rate=learning_rate,
            knowledge_retention=retention,
            adaptation_speed=adaptation,
            prediction_accuracy=accuracy,
            error_rate=error_rate,
            confidence_growth=confidence_growth,
            model_stability=stability
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
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
        
        # Calculate rate of pattern recognition improvement
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-20:]) * np.sqrt(252)
        
        # Learning rate inversely related to volatility
        learning_rate = 1 / (1 + volatility)
        
        return max(0, min(1, learning_rate))
    
    def _calculate_knowledge_retention(self, df: pd.DataFrame) -> float:
        """
        Calculate knowledge retention.
        
        Args:
            df: OHLCV data
            
        Returns:
            Knowledge retention (0-1)
        """
        close = df['close'].values
        
        if len(close) < 30:
            return 0.5
        
        # Calculate autocorrelation as measure of memory
        returns = np.diff(np.log(close))
        autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        
        retention = (autocorr + 1) / 2
        
        return max(0, min(1, retention))
    
    def _calculate_adaptation_speed(self, df: pd.DataFrame) -> float:
        """
        Calculate adaptation speed.
        
        Args:
            df: OHLCV data
            
        Returns:
            Adaptation speed (0-1)
        """
        close = df['close'].values
        
        if len(close) < 20:
            return 0.5
        
        # Calculate how quickly price adapts to new levels
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-20:]) * np.sqrt(252)
        
        if len(returns) >= 40:
            vol_old = np.std(returns[-40:-20]) * np.sqrt(252)
            vol_change = abs(volatility - vol_old) / (vol_old + 1e-10)
            adaptation = 1 / (1 + vol_change)
        else:
            adaptation = 0.5
        
        return max(0, min(1, adaptation))
    
    def _calculate_prediction_accuracy(self, actual: np.ndarray, predictions: List[float]) -> float:
        """
        Calculate prediction accuracy.
        
        Args:
            actual: Actual values
            predictions: Predicted values
            
        Returns:
            Prediction accuracy (0-1)
        """
        if len(actual) == 0 or len(predictions) == 0:
            return 0.5
        
        # Align lengths
        min_len = min(len(actual), len(predictions))
        actual = actual[-min_len:]
        predictions = predictions[-min_len:]
        
        # Calculate directional accuracy
        if min_len < 2:
            return 0.5
        
        actual_direction = np.sign(np.diff(actual))
        pred_direction = np.sign(np.diff(predictions))
        
        correct = np.sum(actual_direction == pred_direction)
        accuracy = correct / len(actual_direction) if len(actual_direction) > 0 else 0.5
        
        return max(0, min(1, accuracy))
    
    def _calculate_error_rate(self, actual: np.ndarray, predictions: List[float]) -> float:
        """
        Calculate error rate.
        
        Args:
            actual: Actual values
            predictions: Predicted values
            
        Returns:
            Error rate (0-1)
        """
        if len(actual) == 0 or len(predictions) == 0:
            return 0.5
        
        # Align lengths
        min_len = min(len(actual), len(predictions))
        actual = actual[-min_len:]
        predictions = predictions[-min_len:]
        
        # Calculate MAE
        mae = np.mean(np.abs(actual - predictions))
        mean_actual = np.mean(actual)
        
        if mean_actual == 0:
            return 0.5
        
        error_rate = mae / abs(mean_actual)
        
        return max(0, min(1, error_rate))
    
    def _calculate_confidence_growth(self, df: pd.DataFrame) -> float:
        """
        Calculate confidence growth.
        
        Args:
            df: OHLCV data
            
        Returns:
            Confidence growth (0-1)
        """
        if len(self.metrics_history) < 2:
            return 0.5
        
        # Calculate improvement in prediction accuracy
        recent_accuracy = self.metrics_history[-1].prediction_accuracy
        old_accuracy = self.metrics_history[0].prediction_accuracy
        
        if old_accuracy == 0:
            return 0.5
        
        growth = (recent_accuracy - old_accuracy) / old_accuracy
        
        return max(0, min(1, growth))
    
    def _calculate_model_stability(self, df: pd.DataFrame) -> float:
        """
        Calculate model stability.
        
        Args:
            df: OHLCV data
            
        Returns:
            Model stability (0-1)
        """
        if len(self.metrics_history) < 5:
            return 0.5
        
        # Calculate variance of recent metrics
        recent_accuracy = [m.prediction_accuracy for m in self.metrics_history[-5:]]
        std_accuracy = np.std(recent_accuracy)
        
        stability = 1 / (1 + std_accuracy)
        
        return max(0, min(1, stability))
    
    def _get_default_metrics(self) -> LearningMetrics:
        """
        Get default metrics.
        
        Returns:
            Default LearningMetrics object
        """
        return LearningMetrics(
            timestamp=datetime.now(),
            learning_rate=0.5,
            knowledge_retention=0.5,
            adaptation_speed=0.5,
            prediction_accuracy=0.5,
            error_rate=0.5,
            confidence_growth=0.0,
            model_stability=0.5
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: LearningMetrics) -> List[LearningSignal]:
        """
        Generate trading signals from learning metrics.
        
        Args:
            df: OHLCV data
            metrics: LearningMetrics object
            
        Returns:
            List of LearningSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check learning status
        if metrics.prediction_accuracy < self.confidence_threshold:
            return signals
        
        # Generate signal based on learning metrics
        if metrics.prediction_accuracy > 0.7 and metrics.learning_rate > 0.6:
            signal_type = 'buy'
            reason = "High prediction accuracy with active learning"
            confidence = metrics.prediction_accuracy
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif metrics.prediction_accuracy < 0.4 and metrics.adaptation_speed > 0.5:
            signal_type = 'sell'
            reason = "Low accuracy with high adaptation"
            confidence = 1 - metrics.prediction_accuracy
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(LearningSignal(
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
                'learning_rate': metrics.learning_rate,
                'retention': metrics.knowledge_retention,
                'stability': metrics.model_stability,
                'error_rate': metrics.error_rate
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: LearningMetrics) -> str:
        """
        Get status from learning metrics.
        
        Args:
            metrics: LearningMetrics object
            
        Returns:
            Status string
        """
        if metrics.prediction_accuracy > 0.7:
            return 'high_learning'
        elif metrics.prediction_accuracy > 0.5:
            return 'moderate_learning'
        else:
            return 'low_learning'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: LearningMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: LearningMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'high_learning': "High learning capacity - predictable patterns",
            'moderate_learning': "Moderate learning capacity",
            'low_learning': "Low learning capacity - uncertain patterns"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get learning metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_accuracy': np.mean([m.prediction_accuracy for m in self.metrics_history]),
            'average_learning_rate': np.mean([m.learning_rate for m in self.metrics_history]),
            'average_adaptation': np.mean([m.adaptation_speed for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_learning_model(config: Optional[Dict[str, Any]] = None) -> LearningModel:
    """
    Create a learning model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        LearningModel instance
    """
    return LearningModel(config)


__all__ = [
    'LearningMetrics',
    'LearningSignal',
    'LearningModel',
    'create_learning_model'
]
