"""
Swing Bot Convergence Model
=============================

This module provides convergence analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ConvergenceMetrics:
    """Convergence metrics data structure."""
    timestamp: datetime
    price_volatility_convergence: float
    indicator_convergence: float
    moving_average_convergence: float
    momentum_convergence: float
    volume_convergence: float
    overall_convergence: float
    divergence_score: float
    trend_strength: float


@dataclass
class ConvergenceSignal:
    """Convergence trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: ConvergenceMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class ConvergenceModel:
    """
    Convergence analysis model for market dynamics.
    
    Implements convergence analysis for various market indicators.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the convergence model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[ConvergenceMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze convergence metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Convergence analysis results
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
    
    def _calculate_metrics(self, df: pd.DataFrame) -> ConvergenceMetrics:
        """
        Calculate convergence metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            ConvergenceMetrics object
        """
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        # Calculate price-volatility convergence
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-self.lookback_period:])
        price_vol_convergence = 1 - min(volatility * 10, 1.0)
        
        # Calculate indicator convergence (using Bollinger Bands)
        ma = np.mean(close[-self.lookback_period:])
        std = np.std(close[-self.lookback_period:])
        bb_upper = ma + 2 * std
        bb_lower = ma - 2 * std
        bb_width = (bb_upper - bb_lower) / ma
        indicator_convergence = 1 - min(bb_width * 5, 1.0)
        
        # Calculate moving average convergence
        ma20 = np.mean(close[-20:]) if len(close) >= 20 else close[-1]
        ma50 = np.mean(close[-50:]) if len(close) >= 50 else close[-1]
        ma_convergence = 1 - abs(ma20 - ma50) / (ma50 + 1e-10)
        
        # Calculate momentum convergence
        momentum1 = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0
        momentum2 = (close[-1] - close[-10]) / close[-10] if len(close) >= 10 else 0
        momentum_convergence = 1 - abs(momentum1 - momentum2)
        
        # Calculate volume convergence
        volume_ma = np.mean(volume[-self.lookback_period:])
        volume_std = np.std(volume[-self.lookback_period:])
        volume_convergence = 1 - min(volume_std / (volume_ma + 1e-10), 1.0)
        
        # Calculate overall convergence
        overall_convergence = np.mean([
            price_vol_convergence,
            indicator_convergence,
            ma_convergence,
            momentum_convergence,
            volume_convergence
        ])
        
        # Calculate divergence score
        divergence_score = 1 - overall_convergence
        
        # Calculate trend strength
        slope, intercept = MathUtils.linear_regression(
            np.arange(len(close[-self.lookback_period:])),
            close[-self.lookback_period:]
        )
        r2 = MathUtils.r_squared(
            np.arange(len(close[-self.lookback_period:])),
            close[-self.lookback_period:]
        )
        trend_strength = r2
        
        metrics = ConvergenceMetrics(
            timestamp=datetime.now(),
            price_volatility_convergence=price_vol_convergence,
            indicator_convergence=indicator_convergence,
            moving_average_convergence=ma_convergence,
            momentum_convergence=momentum_convergence,
            volume_convergence=volume_convergence,
            overall_convergence=overall_convergence,
            divergence_score=divergence_score,
            trend_strength=trend_strength
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _get_default_metrics(self) -> ConvergenceMetrics:
        """
        Get default metrics.
        
        Returns:
            Default ConvergenceMetrics object
        """
        return ConvergenceMetrics(
            timestamp=datetime.now(),
            price_volatility_convergence=0.5,
            indicator_convergence=0.5,
            moving_average_convergence=0.5,
            momentum_convergence=0.5,
            volume_convergence=0.5,
            overall_convergence=0.5,
            divergence_score=0.5,
            trend_strength=0.5
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: ConvergenceMetrics) -> List[ConvergenceSignal]:
        """
        Generate trading signals from convergence metrics.
        
        Args:
            df: OHLCV data
            metrics: ConvergenceMetrics object
            
        Returns:
            List of ConvergenceSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check convergence and divergence
        if metrics.overall_convergence < self.confidence_threshold:
            return signals
        
        # Determine signal based on convergence
        if metrics.overall_convergence > 0.7 and metrics.trend_strength > 0.5:
            # High convergence with strong trend
            signal_type = 'buy'
            reason = "Strong convergence with trend confirmation"
            confidence = metrics.overall_convergence
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif metrics.divergence_score > 0.6 and metrics.trend_strength < 0.3:
            # High divergence with weak trend
            signal_type = 'sell'
            reason = "Divergence with weak trend - potential reversal"
            confidence = metrics.divergence_score
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(ConvergenceSignal(
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
                'overall_convergence': metrics.overall_convergence,
                'divergence_score': metrics.divergence_score,
                'trend_strength': metrics.trend_strength,
                'price_vol_convergence': metrics.price_volatility_convergence,
                'ma_convergence': metrics.moving_average_convergence
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: ConvergenceMetrics) -> str:
        """
        Get status from convergence metrics.
        
        Args:
            metrics: ConvergenceMetrics object
            
        Returns:
            Status string
        """
        if metrics.overall_convergence > 0.7:
            return 'convergent'
        elif metrics.overall_convergence < 0.3:
            return 'divergent'
        else:
            return 'neutral'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: ConvergenceMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: ConvergenceMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'convergent': f'Convergent market (score: {metrics.overall_convergence:.2f})',
            'divergent': f'Divergent market (score: {metrics.overall_convergence:.2f})',
            'neutral': f'Neutral market (score: {metrics.overall_convergence:.2f})'
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get convergence metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_convergence': np.mean([m.overall_convergence for m in self.metrics_history]),
            'average_divergence': np.mean([m.divergence_score for m in self.metrics_history]),
            'average_trend_strength': np.mean([m.trend_strength for m in self.metrics_history]),
            'max_convergence': max([m.overall_convergence for m in self.metrics_history]),
            'min_convergence': min([m.overall_convergence for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_convergence_model(config: Optional[Dict[str, Any]] = None) -> ConvergenceModel:
    """
    Create a convergence model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ConvergenceModel instance
    """
    return ConvergenceModel(config)


__all__ = [
    'ConvergenceMetrics',
    'ConvergenceSignal',
    'ConvergenceModel',
    'create_convergence_model'
]
