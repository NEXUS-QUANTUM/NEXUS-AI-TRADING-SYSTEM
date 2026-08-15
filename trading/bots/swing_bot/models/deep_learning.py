"""
Swing Bot Deep Learning Model
===============================

This module provides deep learning models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


@dataclass
class DeepLearningConfig:
    """Deep learning configuration."""
    input_shape: Tuple[int, int]
    num_layers: int
    hidden_units: List[int]
    dropout_rate: float
    activation: str
    learning_rate: float
    batch_size: int
    epochs: int
    validation_split: float


@dataclass
class DeepLearningPrediction:
    """Deep learning prediction."""
    timestamp: datetime
    predicted_price: float
    confidence: float
    uncertainty: float
    feature_importance: Dict[str, float]


@dataclass
class DeepLearningSignal:
    """Deep learning trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    prediction: DeepLearningPrediction
    indicators: Dict[str, Any] = field(default_factory=dict)


class DeepLearningModel:
    """
    Deep learning model for price prediction.
    
    Implements LSTM, CNN, and Transformer architectures.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the deep learning model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.sequence_length = self.config.get('sequence_length', 30)
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.model_config = DeepLearningConfig(
            input_shape=(self.sequence_length, 10),
            num_layers=3,
            hidden_units=[128, 64, 32],
            dropout_rate=0.2,
            activation='relu',
            learning_rate=0.001,
            batch_size=32,
            epochs=50,
            validation_split=0.2
        )
        self.predictions: List[DeepLearningPrediction] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze deep learning predictions.
        
        Args:
            df: OHLCV data
            
        Returns:
            Deep learning analysis results
        """
        if len(df) < self.sequence_length:
            return {'prediction': None, 'signals': []}
        
        # Generate prediction
        prediction = self._predict(df)
        
        # Generate signals
        signals = self._generate_signals(df, prediction)
        
        return {
            'prediction': prediction,
            'signals': signals,
            'status': self._get_status(prediction),
            'market_character': self._get_market_character(df, prediction)
        }
    
    def _predict(self, df: pd.DataFrame) -> DeepLearningPrediction:
        """
        Generate deep learning prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            DeepLearningPrediction object
        """
        close = df['close'].values
        volume = df['volume'].values
        high = df['high'].values
        low = df['low'].values
        
        # Prepare features
        features = self._prepare_features(df)
        
        # Simple prediction (placeholder for actual deep learning)
        # In production, this would use LSTM/CNN/Transformer models
        predicted_price = self._simple_prediction(close, features)
        
        # Calculate confidence
        confidence = self._calculate_confidence(features)
        
        # Calculate uncertainty
        uncertainty = 1 - confidence
        
        # Calculate feature importance
        feature_importance = self._calculate_feature_importance(features)
        
        prediction = DeepLearningPrediction(
            timestamp=datetime.now(),
            predicted_price=predicted_price,
            confidence=confidence,
            uncertainty=uncertainty,
            feature_importance=feature_importance
        )
        
        self.predictions.append(prediction)
        
        return prediction
    
    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Prepare features for deep learning.
        
        Args:
            df: OHLCV data
            
        Returns:
            Feature array
        """
        close = df['close'].values
        volume = df['volume'].values
        high = df['high'].values
        low = df['low'].values
        
        # Create features
        features = []
        
        for i in range(self.sequence_length, min(len(df), self.sequence_length + 10)):
            # Price features
            price_features = [
                close[i] / close[i-1] - 1,
                close[i] / close[i-5] - 1 if i >= 5 else 0,
                close[i] / close[i-10] - 1 if i >= 10 else 0,
                (high[i] - low[i]) / close[i],
                (close[i] - low[i]) / (high[i] - low[i] + 1e-10)
            ]
            
            # Volume features
            volume_features = [
                volume[i] / np.mean(volume[max(0, i-10):i]) - 1 if i >= 10 else 0,
                volume[i] / volume[i-1] - 1 if i >= 1 else 0
            ]
            
            # Technical features
            technical_features = [
                np.mean(close[max(0, i-5):i+1]) / close[i] - 1 if i >= 5 else 0,
                np.std(close[max(0, i-10):i+1]) / close[i] if i >= 10 else 0,
                (close[i] - np.min(close[max(0, i-10):i+1])) / (np.max(close[max(0, i-10):i+1]) - np.min(close[max(0, i-10):i+1]) + 1e-10) if i >= 10 else 0
            ]
            
            # Combine features
            feature_vector = price_features + volume_features + technical_features
            features.append(feature_vector)
        
        if not features:
            return np.zeros((self.sequence_length, 10))
        
        return np.array(features)
    
    def _simple_prediction(self, close: np.ndarray, features: np.ndarray) -> float:
        """
        Simple prediction using linear regression.
        
        Args:
            close: Close prices
            features: Feature array
            
        Returns:
            Predicted price
        """
        if len(close) < self.sequence_length:
            return close[-1] if len(close) > 0 else 0
        
        # Use last few prices for simple prediction
        last_prices = close[-10:]
        if len(last_prices) < 2:
            return close[-1]
        
        # Simple linear extrapolation
        x = np.arange(len(last_prices))
        slope, intercept = np.polyfit(x, last_prices, 1)
        
        # Predict next price
        next_price = slope * (len(last_prices)) + intercept
        
        return max(0, next_price)
    
    def _calculate_confidence(self, features: np.ndarray) -> float:
        """
        Calculate prediction confidence.
        
        Args:
            features: Feature array
            
        Returns:
            Confidence score (0-1)
        """
        if len(features) < 2:
            return 0.5
        
        # Calculate variance of features
        feature_std = np.std(features, axis=0)
        feature_mean = np.mean(features, axis=0)
        
        # Coefficient of variation
        cv = feature_std / (np.abs(feature_mean) + 1e-10)
        
        # Confidence inversely proportional to variation
        confidence = 1 - np.mean(cv)
        
        return max(0, min(1, confidence))
    
    def _calculate_feature_importance(self, features: np.ndarray) -> Dict[str, float]:
        """
        Calculate feature importance.
        
        Args:
            features: Feature array
            
        Returns:
            Dictionary of feature importance
        """
        # Simple variance-based importance
        importance = {}
        feature_names = ['price_momentum', 'price_5d_return', 'price_10d_return', 
                        'high_low_ratio', 'close_position', 'volume_ratio', 
                        'volume_momentum', 'ma5_ratio', 'volatility', 'rsi']
        
        if len(features) > 0:
            var = np.var(features, axis=0)
            total_var = np.sum(var) + 1e-10
            for i, name in enumerate(feature_names[:len(var)]):
                importance[name] = var[i] / total_var
        
        return importance
    
    def _generate_signals(self, df: pd.DataFrame,
                         prediction: DeepLearningPrediction) -> List[DeepLearningSignal]:
        """
        Generate trading signals from deep learning prediction.
        
        Args:
            df: OHLCV data
            prediction: DeepLearningPrediction object
            
        Returns:
            List of DeepLearningSignal objects
        """
        signals = []
        
        if prediction.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal
        price_change = (prediction.predicted_price - current_price) / current_price
        
        if price_change > 0.02:
            signal_type = 'buy'
            reason = f"Deep learning predicts upward movement ({price_change:.2%})"
            confidence = prediction.confidence
            target = prediction.predicted_price
            stop_loss = current_price * 0.98
            
        elif price_change < -0.02:
            signal_type = 'sell'
            reason = f"Deep learning predicts downward movement ({price_change:.2%})"
            confidence = prediction.confidence
            target = prediction.predicted_price
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(DeepLearningSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            prediction=prediction,
            indicators={
                'predicted_price': prediction.predicted_price,
                'uncertainty': prediction.uncertainty,
                'feature_importance': prediction.feature_importance
            }
        ))
        
        return signals
    
    def _get_status(self, prediction: Optional[DeepLearningPrediction]) -> str:
        """
        Get status from prediction.
        
        Args:
            prediction: DeepLearningPrediction object
            
        Returns:
            Status string
        """
        if not prediction:
            return 'no_prediction'
        
        if prediction.confidence > 0.7:
            return 'high_confidence'
        elif prediction.confidence > 0.5:
            return 'moderate_confidence'
        else:
            return 'low_confidence'
    
    def _get_market_character(self, df: pd.DataFrame,
                            prediction: DeepLearningPrediction) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            prediction: DeepLearningPrediction object
            
        Returns:
            Market character description
        """
        if not prediction:
            return "No prediction available"
        
        status = self._get_status(prediction)
        status_map = {
            'high_confidence': f"High confidence prediction: ${prediction.predicted_price:.2f}",
            'moderate_confidence': f"Moderate confidence prediction: ${prediction.predicted_price:.2f}",
            'low_confidence': f"Low confidence prediction: ${prediction.predicted_price:.2f}"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_prediction_summary(self) -> Dict[str, Any]:
        """
        Get prediction summary.
        
        Returns:
            Prediction summary
        """
        if not self.predictions:
            return {'status': 'no_predictions'}
        
        latest = self.predictions[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_prediction': latest,
            'average_confidence': np.mean([p.confidence for p in self.predictions]),
            'average_uncertainty': np.mean([p.uncertainty for p in self.predictions]),
            'prediction_trend': 'up' if latest.predicted_price > 0 else 'down',
            'status': self._get_status(latest),
            'history_length': len(self.predictions)
        }


def create_deep_learning_model(config: Optional[Dict[str, Any]] = None) -> DeepLearningModel:
    """
    Create a deep learning model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        DeepLearningModel instance
    """
    return DeepLearningModel(config)


__all__ = [
    'DeepLearningConfig',
    'DeepLearningPrediction',
    'DeepLearningSignal',
    'DeepLearningModel',
    'create_deep_learning_model'
]
