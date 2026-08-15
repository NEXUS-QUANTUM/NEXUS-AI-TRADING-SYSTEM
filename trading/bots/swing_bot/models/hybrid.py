"""
Swing Bot Hybrid Model
=======================

This module provides hybrid analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class HybridModelConfig:
    """Hybrid model configuration."""
    models: List[str]
    weights: Dict[str, float]
    combination_method: str  # 'weighted', 'voting', 'stacking'
    validation_split: float
    retraining_frequency: int


@dataclass
class HybridPrediction:
    """Hybrid model prediction."""
    timestamp: datetime
    model_predictions: Dict[str, float]
    combined_prediction: float
    confidence: float
    uncertainty: float
    weights: Dict[str, float]


@dataclass
class HybridSignal:
    """Hybrid trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    prediction: HybridPrediction
    indicators: Dict[str, Any] = field(default_factory=dict)


class HybridModel:
    """
    Hybrid model combining multiple approaches.
    
    Implements ensemble and hybrid modeling techniques.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the hybrid model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.models: Dict[str, Callable] = {}
        self.predictions: List[HybridPrediction] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Model configuration
        self.hybrid_config = HybridModelConfig(
            models=['technical', 'fundamental', 'sentiment', 'momentum'],
            weights={'technical': 0.3, 'fundamental': 0.25, 'sentiment': 0.25, 'momentum': 0.2},
            combination_method='weighted',
            validation_split=0.2,
            retraining_frequency=100
        )
        
        # Register models
        self._register_models()
        
    def _register_models(self) -> None:
        """Register models."""
        self.models['technical'] = self._technical_model
        self.models['fundamental'] = self._fundamental_model
        self.models['sentiment'] = self._sentiment_model
        self.models['momentum'] = self._momentum_model
    
    def _technical_model(self, df: pd.DataFrame) -> float:
        """
        Technical analysis model.
        
        Args:
            df: OHLCV data
            
        Returns:
            Technical score (-1 to 1)
        """
        if len(df) < 20:
            return 0.0
        
        close = df['close'].values
        
        # RSI
        rsi = self._calculate_rsi(close)
        rsi_score = (rsi - 50) / 50
        
        # MACD
        macd = self._calculate_macd(close)
        macd_score = np.tanh(macd)
        
        # Bollinger Bands
        bb_score = self._calculate_bollinger(close)
        
        # Combine
        score = (rsi_score * 0.4 + macd_score * 0.3 + bb_score * 0.3)
        
        return max(-1, min(1, score))
    
    def _fundamental_model(self, df: pd.DataFrame) -> float:
        """
        Fundamental analysis model.
        
        Args:
            df: OHLCV data
            
        Returns:
            Fundamental score (-1 to 1)
        """
        # Placeholder - would use actual fundamental data
        return np.random.normal(0, 0.3)
    
    def _sentiment_model(self, df: pd.DataFrame) -> float:
        """
        Sentiment analysis model.
        
        Args:
            df: OHLCV data
            
        Returns:
            Sentiment score (-1 to 1)
        """
        # Placeholder - would use actual sentiment data
        return np.random.normal(0, 0.3)
    
    def _momentum_model(self, df: pd.DataFrame) -> float:
        """
        Momentum analysis model.
        
        Args:
            df: OHLCV data
            
        Returns:
            Momentum score (-1 to 1)
        """
        if len(df) < 10:
            return 0.0
        
        close = df['close'].values
        
        # Short-term momentum
        short_momentum = (close[-1] - close[-5]) / close[-5] if close[-5] > 0 else 0
        
        # Medium-term momentum
        medium_momentum = (close[-1] - close[-10]) / close[-10] if close[-10] > 0 else 0
        
        # Combine
        momentum = (short_momentum + medium_momentum) / 2
        momentum_score = np.tanh(momentum * 10)
        
        return max(-1, min(1, momentum_score))
    
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
    
    def _calculate_macd(self, close: np.ndarray) -> float:
        """
        Calculate MACD.
        
        Args:
            close: Close prices
            
        Returns:
            MACD value
        """
        if len(close) < 26:
            return 0.0
        
        # Calculate EMAs
        ema12 = self._calculate_ema(close, 12)
        ema26 = self._calculate_ema(close, 26)
        
        if len(ema12) == 0 or len(ema26) == 0:
            return 0.0
        
        return ema12[-1] - ema26[-1]
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate EMA.
        
        Args:
            data: Input data
            period: EMA period
            
        Returns:
            EMA values
        """
        if len(data) < period:
            return np.array([])
        
        alpha = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _calculate_bollinger(self, close: np.ndarray) -> float:
        """
        Calculate Bollinger Bands score.
        
        Args:
            close: Close prices
            
        Returns:
            Bollinger score (-1 to 1)
        """
        if len(close) < 20:
            return 0.0
        
        mean = np.mean(close[-20:])
        std = np.std(close[-20:])
        current = close[-1]
        
        if std == 0:
            return 0.0
        
        zscore = (current - mean) / std
        
        # Normalize to [-1, 1]
        return max(-1, min(1, -zscore / 2))
    
    def predict(self, df: pd.DataFrame) -> HybridPrediction:
        """
        Generate hybrid prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            HybridPrediction object
        """
        predictions = {}
        
        # Get predictions from each model
        for name, model_func in self.models.items():
            try:
                pred = model_func(df)
                predictions[name] = pred
            except Exception:
                predictions[name] = 0.0
        
        # Combine predictions
        combined, confidence, uncertainty = self._combine_predictions(predictions)
        
        prediction = HybridPrediction(
            timestamp=datetime.now(),
            model_predictions=predictions,
            combined_prediction=combined,
            confidence=confidence,
            uncertainty=uncertainty,
            weights=self.hybrid_config.weights
        )
        
        self.predictions.append(prediction)
        
        return prediction
    
    def _combine_predictions(self, predictions: Dict[str, float]) -> Tuple[float, float, float]:
        """
        Combine predictions from multiple models.
        
        Args:
            predictions: Model predictions
            
        Returns:
            Tuple of (combined, confidence, uncertainty)
        """
        if self.hybrid_config.combination_method == 'weighted':
            return self._weighted_combination(predictions)
        elif self.hybrid_config.combination_method == 'voting':
            return self._voting_combination(predictions)
        else:
            return self._weighted_combination(predictions)
    
    def _weighted_combination(self, predictions: Dict[str, float]) -> Tuple[float, float, float]:
        """
        Weighted combination of predictions.
        
        Args:
            predictions: Model predictions
            
        Returns:
            Tuple of (combined, confidence, uncertainty)
        """
        total_weight = sum(self.hybrid_config.weights.values())
        
        if total_weight == 0:
            return 0.0, 0.0, 1.0
        
        combined = 0.0
        for name, pred in predictions.items():
            combined += pred * self.hybrid_config.weights.get(name, 0) / total_weight
        
        # Calculate confidence
        pred_values = list(predictions.values())
        std = np.std(pred_values) if len(pred_values) > 1 else 0
        confidence = 1 / (1 + std)
        confidence = max(0, min(1, confidence))
        
        uncertainty = 1 - confidence
        
        return combined, confidence, uncertainty
    
    def _voting_combination(self, predictions: Dict[str, float]) -> Tuple[float, float, float]:
        """
        Voting combination of predictions.
        
        Args:
            predictions: Model predictions
            
        Returns:
            Tuple of (combined, confidence, uncertainty)
        """
        # Convert to binary signals
        signals = [1 if p > 0 else -1 if p < 0 else 0 for p in predictions.values()]
        
        # Count votes
        positive_votes = sum(1 for s in signals if s == 1)
        negative_votes = sum(1 for s in signals if s == -1)
        neutral_votes = sum(1 for s in signals if s == 0)
        
        total_votes = len(signals)
        
        if positive_votes > negative_votes:
            combined = positive_votes / total_votes
        elif negative_votes > positive_votes:
            combined = -negative_votes / total_votes
        else:
            combined = 0.0
        
        # Calculate confidence
        confidence = max(positive_votes, negative_votes) / total_votes
        uncertainty = 1 - confidence
        
        return combined, confidence, uncertainty
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[HybridSignal]:
        """
        Generate trading signal from hybrid prediction.
        
        Args:
            df: OHLCV data
            
        Returns:
            HybridSignal or None
        """
        prediction = self.predict(df)
        
        if prediction.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal
        if prediction.combined_prediction > 0.3:
            signal_type = 'buy'
            reason = "Hybrid model indicates bullish opportunity"
            confidence = prediction.confidence
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif prediction.combined_prediction < -0.3:
            signal_type = 'sell'
            reason = "Hybrid model indicates bearish opportunity"
            confidence = prediction.confidence
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return None
        
        return HybridSignal(
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
                'model_predictions': prediction.model_predictions,
                'weights': prediction.weights,
                'uncertainty': prediction.uncertainty
            }
        )
    
    def get_hybrid_summary(self) -> Dict[str, Any]:
        """
        Get hybrid model summary.
        
        Returns:
            Hybrid summary
        """
        if not self.predictions:
            return {'status': 'no_predictions'}
        
        latest = self.predictions[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_prediction': latest,
            'total_predictions': len(self.predictions),
            'models': list(self.models.keys()),
            'weights': self.hybrid_config.weights,
            'combination_method': self.hybrid_config.combination_method,
            'average_confidence': np.mean([p.confidence for p in self.predictions]),
            'average_uncertainty': np.mean([p.uncertainty for p in self.predictions]),
            'latest_combined': latest.combined_prediction
        }


def create_hybrid_model(config: Optional[Dict[str, Any]] = None) -> HybridModel:
    """
    Create a hybrid model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        HybridModel instance
    """
    return HybridModel(config)


__all__ = [
    'HybridModelConfig',
    'HybridPrediction',
    'HybridSignal',
    'HybridModel',
    'create_hybrid_model'
]
