"""
Swing Bot Ensemble Model
==========================

This module provides ensemble learning models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class EnsemblePrediction:
    """Ensemble prediction data structure."""
    timestamp: datetime
    predictions: Dict[str, float]  # Model name -> prediction
    aggregated_prediction: float
    confidence: float
    weights: Dict[str, float]
    uncertainty: float
    model_performance: Dict[str, float]


@dataclass
class EnsembleSignal:
    """Ensemble trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    prediction: EnsemblePrediction
    indicators: Dict[str, Any] = field(default_factory=dict)


class EnsembleModel:
    """
    Ensemble learning model for trading predictions.
    
    Combines multiple models for improved accuracy.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ensemble model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.models: Dict[str, Callable] = {}
        self.weights: Dict[str, float] = {}
        self.predictions: List[EnsemblePrediction] = []
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.ensemble_method = self.config.get('ensemble_method', 'weighted_average')
        
        # Register default models
        self._register_default_models()
        
    def _register_default_models(self) -> None:
        """Register default models."""
        # Simple moving average model
        self.register_model('sma', self._sma_prediction, 0.25)
        
        # Exponential moving average model
        self.register_model('ema', self._ema_prediction, 0.25)
        
        # Linear regression model
        self.register_model('linear', self._linear_prediction, 0.25)
        
        # Momentum model
        self.register_model('momentum', self._momentum_prediction, 0.25)
    
    def register_model(self, name: str, model_func: Callable, weight: float = 1.0) -> None:
        """
        Register a model for ensemble.
        
        Args:
            name: Model name
            model_func: Model function
            weight: Model weight
        """
        self.models[name] = model_func
        self.weights[name] = weight
    
    def _sma_prediction(self, data: np.ndarray) -> float:
        """
        Simple Moving Average prediction.
        
        Args:
            data: Price data
            
        Returns:
            Predicted price
        """
        if len(data) < 10:
            return data[-1] if len(data) > 0 else 0
        
        ma = np.mean(data[-10:])
        return ma
    
    def _ema_prediction(self, data: np.ndarray) -> float:
        """
        Exponential Moving Average prediction.
        
        Args:
            data: Price data
            
        Returns:
            Predicted price
        """
        if len(data) < 10:
            return data[-1] if len(data) > 0 else 0
        
        alpha = 2 / (10 + 1)
        ema = data[0]
        
        for i in range(1, len(data)):
            ema = alpha * data[i] + (1 - alpha) * ema
        
        return ema
    
    def _linear_prediction(self, data: np.ndarray) -> float:
        """
        Linear Regression prediction.
        
        Args:
            data: Price data
            
        Returns:
            Predicted price
        """
        if len(data) < 3:
            return data[-1] if len(data) > 0 else 0
        
        x = np.arange(len(data))
        slope, intercept = MathUtils.linear_regression(x, data)
        
        # Predict next value
        next_x = len(data)
        prediction = slope * next_x + intercept
        
        return prediction
    
    def _momentum_prediction(self, data: np.ndarray) -> float:
        """
        Momentum-based prediction.
        
        Args:
            data: Price data
            
        Returns:
            Predicted price
        """
        if len(data) < 5:
            return data[-1] if len(data) > 0 else 0
        
        # Calculate momentum
        momentum = (data[-1] - data[-5]) / data[-5] if data[-5] > 0 else 0
        prediction = data[-1] * (1 + momentum)
        
        return prediction
    
    def predict(self, df: pd.DataFrame) -> EnsemblePrediction:
        """
        Generate ensemble prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            EnsemblePrediction object
        """
        if len(df) < self.lookback_period:
            return self._get_default_prediction()
        
        close = df['close'].values
        predictions = {}
        model_weights = {}
        
        # Get predictions from each model
        for name, model_func in self.models.items():
            try:
                pred = model_func(close)
                predictions[name] = pred
                model_weights[name] = self.weights.get(name, 1.0)
            except Exception:
                predictions[name] = close[-1]
                model_weights[name] = 0.1
        
        # Aggregate predictions
        aggregated, confidence, uncertainty = self._aggregate_predictions(predictions, model_weights)
        
        # Calculate model performance
        performance = self._calculate_model_performance(predictions, close[-1])
        
        prediction = EnsemblePrediction(
            timestamp=datetime.now(),
            predictions=predictions,
            aggregated_prediction=aggregated,
            confidence=confidence,
            weights=model_weights,
            uncertainty=uncertainty,
            model_performance=performance
        )
        
        self.predictions.append(prediction)
        
        return prediction
    
    def _aggregate_predictions(self, predictions: Dict[str, float],
                             weights: Dict[str, float]) -> Tuple[float, float, float]:
        """
        Aggregate predictions using ensemble method.
        
        Args:
            predictions: Model predictions
            weights: Model weights
            
        Returns:
            Tuple of (aggregated, confidence, uncertainty)
        """
        if self.ensemble_method == 'weighted_average':
            return self._weighted_average(predictions, weights)
        elif self.ensemble_method == 'median':
            return self._median_aggregation(predictions)
        elif self.ensemble_method == 'consensus':
            return self._consensus_aggregation(predictions)
        else:
            return self._weighted_average(predictions, weights)
    
    def _weighted_average(self, predictions: Dict[str, float],
                         weights: Dict[str, float]) -> Tuple[float, float, float]:
        """
        Weighted average aggregation.
        
        Args:
            predictions: Model predictions
            weights: Model weights
            
        Returns:
            Tuple of (aggregated, confidence, uncertainty)
        """
        total_weight = sum(weights.values())
        
        if total_weight == 0:
            return 0.0, 0.0, 1.0
        
        aggregated = 0.0
        for name, pred in predictions.items():
            aggregated += pred * weights.get(name, 0.0) / total_weight
        
        # Calculate confidence
        pred_values = list(predictions.values())
        std = np.std(pred_values) if len(pred_values) > 1 else 0
        confidence = 1 / (1 + std / (abs(aggregated) + 1e-10))
        confidence = max(0, min(1, confidence))
        
        # Calculate uncertainty
        uncertainty = 1 - confidence
        
        return aggregated, confidence, uncertainty
    
    def _median_aggregation(self, predictions: Dict[str, float]) -> Tuple[float, float, float]:
        """
        Median aggregation.
        
        Args:
            predictions: Model predictions
            
        Returns:
            Tuple of (aggregated, confidence, uncertainty)
        """
        pred_values = list(predictions.values())
        aggregated = np.median(pred_values)
        
        # Calculate confidence
        std = np.std(pred_values) if len(pred_values) > 1 else 0
        confidence = 1 / (1 + std / (abs(aggregated) + 1e-10))
        confidence = max(0, min(1, confidence))
        
        uncertainty = 1 - confidence
        
        return aggregated, confidence, uncertainty
    
    def _consensus_aggregation(self, predictions: Dict[str, float]) -> Tuple[float, float, float]:
        """
        Consensus aggregation.
        
        Args:
            predictions: Model predictions
            
        Returns:
            Tuple of (aggregated, confidence, uncertainty)
        """
        pred_values = list(predictions.values())
        
        # Find consensus (values within 2% of each other)
        consensus_count = 0
        consensus_sum = 0
        
        for i, val1 in enumerate(pred_values):
            for j, val2 in enumerate(pred_values):
                if i != j and abs(val1 - val2) / (abs(val1) + 1e-10) < 0.02:
                    consensus_count += 1
                    consensus_sum += val1
        
        if consensus_count > 0:
            aggregated = consensus_sum / consensus_count
        else:
            aggregated = np.mean(pred_values)
        
        # Calculate confidence
        std = np.std(pred_values) if len(pred_values) > 1 else 0
        confidence = 1 / (1 + std / (abs(aggregated) + 1e-10))
        confidence = max(0, min(1, confidence))
        
        uncertainty = 1 - confidence
        
        return aggregated, confidence, uncertainty
    
    def _calculate_model_performance(self, predictions: Dict[str, float],
                                  actual: float) -> Dict[str, float]:
        """
        Calculate model performance metrics.
        
        Args:
            predictions: Model predictions
            actual: Actual value
            
        Returns:
            Performance metrics
        """
        performance = {}
        
        for name, pred in predictions.items():
            if actual != 0:
                error = abs(pred - actual) / abs(actual)
                performance[name] = 1 / (1 + error)
            else:
                performance[name] = 0.5
        
        return performance
    
    def _get_default_prediction(self) -> EnsemblePrediction:
        """
        Get default prediction.
        
        Returns:
            Default EnsemblePrediction object
        """
        return EnsemblePrediction(
            timestamp=datetime.now(),
            predictions={},
            aggregated_prediction=0.0,
            confidence=0.5,
            weights={},
            uncertainty=0.5,
            model_performance={}
        )
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[EnsembleSignal]:
        """
        Generate trading signal from ensemble prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            EnsembleSignal or None
        """
        prediction = self.predict(df)
        
        if prediction.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal
        price_change = (prediction.aggregated_prediction - current_price) / current_price
        
        if price_change > 0.02:
            signal_type = 'buy'
            reason = f"Ensemble predicts upward movement ({price_change:.2%})"
            confidence = prediction.confidence
            target = prediction.aggregated_prediction
            stop_loss = current_price * 0.98
            
        elif price_change < -0.02:
            signal_type = 'sell'
            reason = f"Ensemble predicts downward movement ({price_change:.2%})"
            confidence = prediction.confidence
            target = prediction.aggregated_prediction
            stop_loss = current_price * 1.02
            
        else:
            return None
        
        return EnsembleSignal(
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
                'model_predictions': prediction.predictions,
                'weights': prediction.weights,
                'uncertainty': prediction.uncertainty
            }
        )
    
    def get_ensemble_summary(self) -> Dict[str, Any]:
        """
        Get ensemble summary.
        
        Returns:
            Ensemble summary
        """
        if not self.predictions:
            return {'status': 'no_predictions'}
        
        latest = self.predictions[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_prediction': latest,
            'total_predictions': len(self.predictions),
            'models': list(self.models.keys()),
            'weights': self.weights,
            'average_confidence': np.mean([p.confidence for p in self.predictions]),
            'average_uncertainty': np.mean([p.uncertainty for p in self.predictions]),
            'current_weights': self.weights,
            'latest_aggregated': latest.aggregated_prediction
        }


def create_ensemble_model(config: Optional[Dict[str, Any]] = None) -> EnsembleModel:
    """
    Create an ensemble model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        EnsembleModel instance
    """
    return EnsembleModel(config)


__all__ = [
    'EnsemblePrediction',
    'EnsembleSignal',
    'EnsembleModel',
    'create_ensemble_model'
]
