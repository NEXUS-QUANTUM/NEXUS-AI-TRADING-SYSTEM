"""
Swing Bot Forecast Model
==========================

This module provides forecasting models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from trading.bots.swing_bot.utils.math_utils import MathUtils
import warnings
warnings.filterwarnings('ignore')


@dataclass
class ForecastResult:
    """Forecast result data structure."""
    timestamp: datetime
    forecast_horizon: int
    point_forecast: float
    lower_bound: float
    upper_bound: float
    confidence_level: float
    trend: str  # 'up', 'down', 'sideways'
    strength: float
    seasonality: float


@dataclass
class ForecastSignal:
    """Forecast trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    forecast: ForecastResult
    indicators: Dict[str, Any] = field(default_factory=dict)


class ForecastModel:
    """
    Forecasting model for price prediction.
    
    Implements various forecasting techniques.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the forecast model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.forecast_horizon = self.config.get('forecast_horizon', 10)
        self.confidence_level = self.config.get('confidence_level', 0.95)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.forecasts: List[ForecastResult] = []
        
    def forecast(self, df: pd.DataFrame) -> ForecastResult:
        """
        Generate forecast for price.
        
        Args:
            df: OHLCV data
            
        Returns:
            ForecastResult object
        """
        if len(df) < self.lookback_period:
            return self._get_default_forecast()
        
        close = df['close'].values
        
        # Use multiple forecasting methods
        forecasts = []
        
        # 1. Linear regression
        x = np.arange(len(close))
        slope, intercept = MathUtils.linear_regression(x, close)
        lin_forecast = slope * (len(close) + self.forecast_horizon) + intercept
        
        # 2. Exponential smoothing
        alpha = 0.3
        smoothed = close[0]
        for i in range(1, len(close)):
            smoothed = alpha * close[i] + (1 - alpha) * smoothed
        exp_forecast = smoothed
        
        # 3. Moving average
        ma = np.mean(close[-10:])
        ma_forecast = ma
        
        # 4. Momentum-based
        momentum = (close[-1] - close[-5]) / close[-5] if close[-5] > 0 else 0
        mom_forecast = close[-1] * (1 + momentum)
        
        # Combine forecasts
        combined_forecast = np.mean([lin_forecast, exp_forecast, ma_forecast, mom_forecast])
        
        # Calculate confidence
        forecast_values = [lin_forecast, exp_forecast, ma_forecast, mom_forecast]
        std = np.std(forecast_values)
        confidence = 1 / (1 + std / (abs(combined_forecast) + 1e-10))
        
        # Calculate bounds
        z_score = 1.96  # For 95% confidence
        lower_bound = combined_forecast - z_score * std
        upper_bound = combined_forecast + z_score * std
        
        # Determine trend
        trend = 'sideways'
        if slope > 0.01:
            trend = 'up'
        elif slope < -0.01:
            trend = 'down'
        
        # Calculate strength
        strength = min(abs(slope) * 10, 1.0)
        
        # Calculate seasonality
        seasonality = self._calculate_seasonality(close)
        
        result = ForecastResult(
            timestamp=datetime.now(),
            forecast_horizon=self.forecast_horizon,
            point_forecast=combined_forecast,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            confidence_level=confidence,
            trend=trend,
            strength=strength,
            seasonality=seasonality
        )
        
        self.forecasts.append(result)
        
        return result
    
    def _calculate_seasonality(self, data: np.ndarray) -> float:
        """
        Calculate seasonality strength.
        
        Args:
            data: Time series data
            
        Returns:
            Seasonality strength
        """
        if len(data) < 50:
            return 0.0
        
        # Check for weekly patterns (assuming daily data)
        weekly_patterns = []
        
        for i in range(7, len(data)):
            weekly_patterns.append(data[i] - data[i-7])
        
        if not weekly_patterns:
            return 0.0
        
        # Calculate seasonality strength
        seasonality = np.std(weekly_patterns) / np.std(data)
        
        return min(seasonality, 1.0)
    
    def _get_default_forecast(self) -> ForecastResult:
        """
        Get default forecast.
        
        Returns:
            Default ForecastResult object
        """
        return ForecastResult(
            timestamp=datetime.now(),
            forecast_horizon=self.forecast_horizon,
            point_forecast=0.0,
            lower_bound=0.0,
            upper_bound=0.0,
            confidence_level=0.0,
            trend='sideways',
            strength=0.0,
            seasonality=0.0
        )
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[ForecastSignal]:
        """
        Generate trading signal from forecast.
        
        Args:
            df: OHLCV data
            
        Returns:
            ForecastSignal or None
        """
        forecast = self.forecast(df)
        
        if forecast.confidence_level < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal based on forecast
        price_change = (forecast.point_forecast - current_price) / current_price
        
        if price_change > 0.02 and forecast.trend == 'up':
            signal_type = 'buy'
            reason = f"Forecast predicts upward movement ({price_change:.2%})"
            confidence = forecast.confidence_level
            target = forecast.point_forecast
            stop_loss = current_price * 0.98
            
        elif price_change < -0.02 and forecast.trend == 'down':
            signal_type = 'sell'
            reason = f"Forecast predicts downward movement ({price_change:.2%})"
            confidence = forecast.confidence_level
            target = forecast.point_forecast
            stop_loss = current_price * 1.02
            
        else:
            return None
        
        return ForecastSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            forecast=forecast,
            indicators={
                'forecast_price': forecast.point_forecast,
                'lower_bound': forecast.lower_bound,
                'upper_bound': forecast.upper_bound,
                'trend': forecast.trend,
                'seasonality': forecast.seasonality
            }
        )
    
    def get_forecast_summary(self) -> Dict[str, Any]:
        """
        Get forecast summary.
        
        Returns:
            Forecast summary
        """
        if not self.forecasts:
            return {'status': 'no_forecasts'}
        
        latest = self.forecasts[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_forecast': latest,
            'total_forecasts': len(self.forecasts),
            'average_confidence': np.mean([f.confidence_level for f in self.forecasts]),
            'average_strength': np.mean([f.strength for f in self.forecasts]),
            'trend_distribution': {
                'up': len([f for f in self.forecasts if f.trend == 'up']),
                'down': len([f for f in self.forecasts if f.trend == 'down']),
                'sideways': len([f for f in self.forecasts if f.trend == 'sideways'])
            },
            'latest_forecast_price': latest.point_forecast,
            'latest_confidence': latest.confidence_level
        }


def create_forecast_model(config: Optional[Dict[str, Any]] = None) -> ForecastModel:
    """
    Create a forecast model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ForecastModel instance
    """
    return ForecastModel(config)


__all__ = [
    'ForecastResult',
    'ForecastSignal',
    'ForecastModel',
    'create_forecast_model'
]
