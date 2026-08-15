"""
Swing Bot Machine Learning Model
==================================

This module provides machine learning models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')


@dataclass
class MLPrediction:
    """Machine learning prediction data structure."""
    timestamp: datetime
    predicted_price: float
    confidence: float
    feature_importance: Dict[str, float]
    model_type: str
    error: float
    r2_score: float


@dataclass
class MLSignal:
    """Machine learning trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    prediction: MLPrediction
    indicators: Dict[str, Any] = field(default_factory=dict)


class MachineLearningModel:
    """
    Machine learning model for price prediction.
    
    Implements various ML algorithms for trading predictions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the machine learning model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.model_type = self.config.get('model_type', 'random_forest')
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.models = {}
        self.scaler = StandardScaler()
        self.predictions: List[MLPrediction] = []
        
        # Initialize models
        self._initialize_models()
        
    def _initialize_models(self) -> None:
        """Initialize machine learning models."""
        self.models['linear'] = LinearRegression()
        self.models['ridge'] = Ridge(alpha=1.0)
        self.models['lasso'] = Lasso(alpha=0.1)
        self.models['random_forest'] = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.models['gradient_boosting'] = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare features for machine learning.
        
        Args:
            df: OHLCV data
            
        Returns:
            Tuple of (features, target)
        """
        if len(df) < self.lookback_period:
            return np.array([]), np.array([])
        
        close = df['close'].values
        volume = df['volume'].values
        high = df['high'].values
        low = df['low'].values
        
        # Create features
        features = []
        targets = []
        
        for i in range(self.lookback_period, len(close) - 1):
            # Price features
            price_features = [
                close[i] / close[i-1] - 1,
                close[i] / close[i-5] - 1 if i >= 5 else 0,
                close[i] / close[i-10] - 1 if i >= 10 else 0,
                close[i] / close[i-20] - 1 if i >= 20 else 0,
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
            targets.append(close[i+1] / close[i] - 1)  # Next day return
        
        return np.array(features), np.array(targets)
    
    def train(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Train machine learning models.
        
        Args:
            df: OHLCV data
            
        Returns:
            Training metrics
        """
        features, targets = self.prepare_features(df)
        
        if len(features) < 10:
            return {'status': 'insufficient_data'}
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, targets, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train each model
        results = {}
        
        for name, model in self.models.items():
            model.fit(X_train_scaled, y_train)
            
            # Evaluate
            y_pred = model.predict(X_test_scaled)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            results[name] = {
                'mse': mse,
                'r2': r2,
                'model': model
            }
        
        return results
    
    def predict(self, df: pd.DataFrame) -> MLPrediction:
        """
        Generate prediction using trained models.
        
        Args:
            df: OHLCV data
            
        Returns:
            MLPrediction object
        """
        if len(df) < self.lookback_period:
            return self._get_default_prediction()
        
        # Prepare features
        features, _ = self.prepare_features(df)
        
        if len(features) == 0:
            return self._get_default_prediction()
        
        # Get latest features
        latest_features = features[-1].reshape(1, -1)
        latest_features_scaled = self.scaler.transform(latest_features)
        
        # Get predictions from all models
        predictions = {}
        
        for name, model in self.models.items():
            try:
                pred = model.predict(latest_features_scaled)[0]
                predictions[name] = pred
            except:
                predictions[name] = 0.0
        
        # Average predictions
        avg_prediction = np.mean(list(predictions.values()))
        
        # Calculate confidence
        confidence = 1 - np.std(list(predictions.values()))
        confidence = max(0, min(1, confidence))
        
        # Get feature importance (using random forest)
        feature_importance = {}
        if 'random_forest' in self.models:
            rf_model = self.models['random_forest']
            if hasattr(rf_model, 'feature_importances_'):
                feature_names = ['price_momentum', 'price_5d_return', 'price_10d_return', 
                               'price_20d_return', 'high_low_ratio', 'close_position',
                               'volume_ratio', 'volume_momentum', 'ma5_ratio', 'volatility', 'rsi']
                for i, name in enumerate(feature_names[:len(rf_model.feature_importances_)]):
                    feature_importance[name] = rf_model.feature_importances_[i]
        
        current_price = df['close'].iloc[-1]
        predicted_price = current_price * (1 + avg_prediction)
        
        # Calculate error
        error = abs(avg_prediction)
        
        prediction = MLPrediction(
            timestamp=datetime.now(),
            predicted_price=predicted_price,
            confidence=confidence,
            feature_importance=feature_importance,
            model_type=self.model_type,
            error=error,
            r2_score=0  # Placeholder
        )
        
        self.predictions.append(prediction)
        
        return prediction
    
    def _get_default_prediction(self) -> MLPrediction:
        """
        Get default prediction.
        
        Returns:
            Default MLPrediction object
        """
        return MLPrediction(
            timestamp=datetime.now(),
            predicted_price=0.0,
            confidence=0.0,
            feature_importance={},
            model_type='none',
            error=0.0,
            r2_score=0.0
        )
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[MLSignal]:
        """
        Generate trading signal from machine learning prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            MLSignal or None
        """
        prediction = self.predict(df)
        
        if prediction.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal
        price_change = (prediction.predicted_price - current_price) / current_price
        
        if price_change > 0.02:
            signal_type = 'buy'
            reason = f"ML predicts upward movement ({price_change:.2%})"
            confidence = prediction.confidence
            target = prediction.predicted_price
            stop_loss = current_price * 0.98
            
        elif price_change < -0.02:
            signal_type = 'sell'
            reason = f"ML predicts downward movement ({price_change:.2%})"
            confidence = prediction.confidence
            target = prediction.predicted_price
            stop_loss = current_price * 1.02
            
        else:
            return None
        
        return MLSignal(
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
                'feature_importance': prediction.feature_importance,
                'model_type': prediction.model_type,
                'error': prediction.error
            }
        )
    
    def get_ml_summary(self) -> Dict[str, Any]:
        """
        Get machine learning summary.
        
        Returns:
            ML summary
        """
        if not self.predictions:
            return {'status': 'no_predictions'}
        
        latest = self.predictions[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_prediction': latest,
            'total_predictions': len(self.predictions),
            'average_confidence': np.mean([p.confidence for p in self.predictions]),
            'average_error': np.mean([p.error for p in self.predictions]),
            'model_type': self.model_type,
            'feature_importance': latest.feature_importance
        }


def create_machine_learning_model(config: Optional[Dict[str, Any]] = None) -> MachineLearningModel:
    """
    Create a machine learning model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        MachineLearningModel instance
    """
    return MachineLearningModel(config)


__all__ = [
    'MLPrediction',
    'MLSignal',
    'MachineLearningModel',
    'create_machine_learning_model'
]
