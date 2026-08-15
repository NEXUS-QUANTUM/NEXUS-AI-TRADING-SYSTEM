"""
Swing Bot Predictive Model
============================

This module provides predictive analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')


@dataclass
class Prediction:
    """Prediction data structure."""
    timestamp: datetime
    target: str
    predicted_value: float
    actual_value: Optional[float] = None
    confidence: float = 0.5
    error: Optional[float] = None
    features: Dict[str, float] = field(default_factory=dict)


@dataclass
class PredictiveSignal:
    """Predictive trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    prediction: Prediction
    indicators: Dict[str, Any] = field(default_factory=dict)


class PredictiveModel:
    """
    Predictive analysis model for price forecasting.
    
    Implements various prediction techniques for trading signals.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the predictive model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.prediction_horizon = self.config.get('prediction_horizon', 5)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Model state
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.predictions: List[Prediction] = []
        self.history: Dict[str, List[float]] = {}
        
    def predict(self, df: pd.DataFrame) -> Prediction:
        """
        Generate price prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            Prediction object
        """
        if len(df) < self.lookback_period:
            return self._get_default_prediction(df)
        
        # Prepare features
        features = self._prepare_features(df)
        
        # Get prediction
        predicted_price, confidence = self._predict_price(df, features)
        
        prediction = Prediction(
            timestamp=datetime.now(),
            target='price',
            predicted_value=predicted_price,
            confidence=confidence,
            features=features
        )
        
        self.predictions.append(prediction)
        
        return prediction
    
    def _prepare_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Prepare features for prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            Feature dictionary
        """
        close = df['close'].values
        volume = df['volume'].values
        
        features = {}
        
        # Price features
        features['price_change'] = (close[-1] - close[-self.lookback_period]) / close[-self.lookback_period]
        features['price_volatility'] = np.std(close[-self.lookback_period:]) / np.mean(close[-self.lookback_period:])
        
        # Volume features
        features['volume_change'] = (volume[-1] - np.mean(volume[-self.lookback_period:])) / np.mean(volume[-self.lookback_period:])
        features['volume_ratio'] = volume[-1] / np.mean(volume[-self.lookback_period:])
        
        # Technical features
        ma10 = np.mean(close[-10:]) if len(close) >= 10 else close[-1]
        ma20 = np.mean(close[-20:]) if len(close) >= 20 else close[-1]
        ma50 = np.mean(close[-50:]) if len(close) >= 50 else close[-1]
        
        features['ma_ratio_10_20'] = ma10 / ma20 if ma20 > 0 else 1
        features['ma_ratio_20_50'] = ma20 / ma50 if ma50 > 0 else 1
        
        # Momentum features
        returns = np.diff(np.log(close))
        features['momentum'] = np.mean(returns[-10:]) if len(returns) >= 10 else 0
        features['momentum_std'] = np.std(returns[-10:]) if len(returns) >= 10 else 0
        
        # RSI
        features['rsi'] = self._calculate_rsi(close)
        
        return features
    
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
    
    def _predict_price(self, df: pd.DataFrame, features: Dict[str, float]) -> Tuple[float, float]:
        """
        Predict price using features.
        
        Args:
            df: OHLCV data
            features: Feature dictionary
            
        Returns:
            Tuple of (predicted_price, confidence)
        """
        close = df['close'].values
        
        # Simple linear regression
        x = np.arange(len(close[-self.lookback_period:])).reshape(-1, 1)
        y = close[-self.lookback_period:]
        
        # Fit model
        model = LinearRegression()
        model.fit(x, y)
        
        # Predict next value
        next_x = np.array([[len(y)]])
        predicted_price = model.predict(next_x)[0]
        
        # Calculate confidence
        r2 = model.score(x, y)
        confidence = 0.3 + 0.7 * r2
        
        # Adjust confidence with other factors
        confidence *= (1 + 0.2 * min(features.get('momentum', 0), 0.1))
        confidence *= (1 - 0.1 * min(features.get('price_volatility', 0), 0.5))
        
        confidence = min(max(confidence, 0.1), 0.95)
        
        return predicted_price, confidence
    
    def _get_default_prediction(self, df: pd.DataFrame) -> Prediction:
        """
        Get default prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            Default Prediction object
        """
        close = df['close'].values if len(df) > 0 else [100]
        current_price = close[-1]
        
        return Prediction(
            timestamp=datetime.now(),
            target='price',
            predicted_value=current_price * 1.01,
            confidence=0.5,
            features={}
        )
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[PredictiveSignal]:
        """
        Generate trading signal from prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            PredictiveSignal or None
        """
        prediction = self.predict(df)
        
        if prediction.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal type
        if prediction.predicted_value > current_price * 1.02:
            signal_type = 'buy'
            reason = "Predictive model forecasts upward movement"
            target = prediction.predicted_value
            stop_loss = current_price * 0.98
        elif prediction.predicted_value < current_price * 0.98:
            signal_type = 'sell'
            reason = "Predictive model forecasts downward movement"
            target = prediction.predicted_value
            stop_loss = current_price * 1.02
        else:
            return None
        
        return PredictiveSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=prediction.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            prediction=prediction,
            indicators={
                'predicted_price': prediction.predicted_value,
                'price_change': (prediction.predicted_value - current_price) / current_price,
                'features': prediction.features
            }
        )
    
    def evaluate_predictions(self) -> Dict[str, Any]:
        """
        Evaluate prediction accuracy.
        
        Returns:
            Evaluation metrics
        """
        if len(self.predictions) < 2:
            return {'status': 'insufficient_data'}
        
        # Calculate metrics
        errors = [p.error for p in self.predictions if p.error is not None]
        
        if not errors:
            return {'status': 'no_completed_predictions'}
        
        metrics = {
            'total_predictions': len(self.predictions),
            'completed_predictions': len(errors),
            'mean_error': np.mean(errors),
            'std_error': np.std(errors),
            'mean_absolute_error': np.mean(np.abs(errors)),
            'mean_squared_error': np.mean(np.array(errors) ** 2),
            'root_mean_squared_error': np.sqrt(np.mean(np.array(errors) ** 2)),
            'accuracy': len([e for e in errors if abs(e) < 0.02]) / len(errors) if errors else 0
        }
        
        return metrics
    
    def update_actual(self, actual_price: float) -> None:
        """
        Update predictions with actual values.
        
        Args:
            actual_price: Actual price value
        """
        if self.predictions:
            latest_prediction = self.predictions[-1]
            latest_prediction.actual_value = actual_price
            latest_prediction.error = (actual_price - latest_prediction.predicted_value) / latest_prediction.predicted_value


def create_predictive_model(config: Optional[Dict[str, Any]] = None) -> PredictiveModel:
    """
    Create a predictive model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        PredictiveModel instance
    """
    return PredictiveModel(config)


__all__ = [
    'Prediction',
    'PredictiveSignal',
    'PredictiveModel',
    'create_predictive_model'
]
