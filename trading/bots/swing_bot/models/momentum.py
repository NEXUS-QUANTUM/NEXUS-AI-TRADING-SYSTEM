"""
Swing Bot Momentum Model
==========================

This module provides momentum analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class MomentumMetrics:
    """Momentum metrics data structure."""
    timestamp: datetime
    price_momentum: float
    volume_momentum: float
    relative_momentum: float
    momentum_score: float
    acceleration: float
    velocity: float
    rsi: float
    macd: float
    stochastic: float


@dataclass
class MomentumSignal:
    """Momentum trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: MomentumMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class MomentumModel:
    """
    Momentum analysis model for trend identification.
    
    Implements momentum-based trading strategies.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the momentum model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 20)
        self.momentum_threshold = self.config.get('momentum_threshold', 0.02)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[MomentumMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze momentum patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Momentum analysis results
        """
        if len(df) < self.lookback_period:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
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
    
    def _calculate_metrics(self, df: pd.DataFrame) -> MomentumMetrics:
        """
        Calculate momentum metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            MomentumMetrics object
        """
        close = df['close'].values
        volume = df['volume'].values
        
        # Price momentum
        price_momentum = (close[-1] - close[-self.lookback_period]) / close[-self.lookback_period]
        
        # Volume momentum
        volume_ma = np.mean(volume[-self.lookback_period:])
        volume_momentum = (volume[-1] - volume_ma) / volume_ma if volume_ma > 0 else 0
        
        # Relative momentum (compared to benchmark)
        # This would use actual benchmark data in production
        relative_momentum = price_momentum
        
        # Combined momentum score
        momentum_score = price_momentum * 0.5 + volume_momentum * 0.3 + relative_momentum * 0.2
        
        # Acceleration (rate of momentum change)
        if len(close) >= self.lookback_period + 5:
            prev_momentum = (close[-self.lookback_period - 5] - close[-self.lookback_period - 10]) / close[-self.lookback_period - 10]
            acceleration = price_momentum - prev_momentum
        else:
            acceleration = 0.0
        
        # Velocity (speed of price change)
        if len(close) >= 5:
            velocity = (close[-1] - close[-5]) / close[-5]
        else:
            velocity = 0.0
        
        # RSI
        rsi = self._calculate_rsi(close)
        
        # MACD
        macd = self._calculate_macd(close)
        
        # Stochastic
        stochastic = self._calculate_stochastic(df)
        
        metrics = MomentumMetrics(
            timestamp=datetime.now(),
            price_momentum=price_momentum,
            volume_momentum=volume_momentum,
            relative_momentum=relative_momentum,
            momentum_score=momentum_score,
            acceleration=acceleration,
            velocity=velocity,
            rsi=rsi,
            macd=macd,
            stochastic=stochastic
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
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
    
    def _calculate_stochastic(self, df: pd.DataFrame) -> float:
        """
        Calculate Stochastic Oscillator.
        
        Args:
            df: OHLCV data
            
        Returns:
            Stochastic value
        """
        if len(df) < 14:
            return 50.0
        
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # Calculate highest high and lowest low over last 14 periods
        highest_high = np.max(high[-14:])
        lowest_low = np.min(low[-14:])
        
        if highest_high == lowest_low:
            return 50.0
        
        # Calculate stochastic
        k = 100 * (close[-1] - lowest_low) / (highest_high - lowest_low)
        
        return k
    
    def _get_default_metrics(self) -> MomentumMetrics:
        """
        Get default metrics.
        
        Returns:
            Default MomentumMetrics object
        """
        return MomentumMetrics(
            timestamp=datetime.now(),
            price_momentum=0.0,
            volume_momentum=0.0,
            relative_momentum=0.0,
            momentum_score=0.0,
            acceleration=0.0,
            velocity=0.0,
            rsi=50.0,
            macd=0.0,
            stochastic=50.0
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: MomentumMetrics) -> List[MomentumSignal]:
        """
        Generate momentum signals.
        
        Args:
            df: OHLCV data
            metrics: MomentumMetrics object
            
        Returns:
            List of MomentumSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Calculate signal strength
        signal_strength = abs(metrics.momentum_score)
        
        if signal_strength < self.confidence_threshold:
            return signals
        
        # Determine signal type
        if metrics.momentum_score > self.momentum_threshold:
            signal_type = 'buy'
            reason = f"Positive momentum detected ({metrics.momentum_score:.2%})"
            confidence = min(signal_strength, 1.0)
            target = current_price * (1 + confidence * 0.05)
            stop_loss = current_price * (1 - confidence * 0.03)
            
            signals.append(MomentumSignal(
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
                    'rsi': metrics.rsi,
                    'macd': metrics.macd,
                    'stochastic': metrics.stochastic,
                    'acceleration': metrics.acceleration
                }
            ))
            
        elif metrics.momentum_score < -self.momentum_threshold:
            signal_type = 'sell'
            reason = f"Negative momentum detected ({metrics.momentum_score:.2%})"
            confidence = min(signal_strength, 1.0)
            target = current_price * (1 - confidence * 0.05)
            stop_loss = current_price * (1 + confidence * 0.03)
            
            signals.append(MomentumSignal(
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
                    'rsi': metrics.rsi,
                    'macd': metrics.macd,
                    'stochastic': metrics.stochastic,
                    'acceleration': metrics.acceleration
                }
            ))
        
        return signals
    
    def _get_status(self, metrics: MomentumMetrics) -> str:
        """
        Get status from momentum metrics.
        
        Args:
            metrics: MomentumMetrics object
            
        Returns:
            Status string
        """
        if metrics.momentum_score > 0.03:
            return 'strong_bullish'
        elif metrics.momentum_score > 0.01:
            return 'moderate_bullish'
        elif metrics.momentum_score > -0.01:
            return 'neutral'
        elif metrics.momentum_score > -0.03:
            return 'moderate_bearish'
        else:
            return 'strong_bearish'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: MomentumMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: MomentumMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'strong_bullish': 'Strong upward momentum',
            'moderate_bullish': 'Moderate upward momentum',
            'neutral': 'Neutral momentum',
            'moderate_bearish': 'Moderate downward momentum',
            'strong_bearish': 'Strong downward momentum'
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get momentum metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_momentum': np.mean([m.momentum_score for m in self.metrics_history]),
            'max_momentum': max([m.momentum_score for m in self.metrics_history]),
            'min_momentum': min([m.momentum_score for m in self.metrics_history]),
            'average_rsi': np.mean([m.rsi for m in self.metrics_history]),
            'average_macd': np.mean([m.macd for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_momentum_model(config: Optional[Dict[str, Any]] = None) -> MomentumModel:
    """
    Create a momentum model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        MomentumModel instance
    """
    return MomentumModel(config)


__all__ = [
    'MomentumMetrics',
    'MomentumSignal',
    'MomentumModel',
    'create_momentum_model'
]
