"""
Swing Bot Reversion Model
===========================

This module provides mean reversion analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ReversionMetrics:
    """Mean reversion metrics data structure."""
    timestamp: datetime
    zscore: float
    mean: float
    std: float
    current_price: float
    mean_reversion_score: float
    half_life: float
    deviation: float
    confidence: float


@dataclass
class ReversionSignal:
    """Mean reversion trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: ReversionMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class ReversionModel:
    """
    Mean reversion analysis model for price corrections.
    
    Implements statistical mean reversion strategies.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the reversion model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.entry_zscore = self.config.get('entry_zscore', 2.0)
        self.exit_zscore = self.config.get('exit_zscore', 0.5)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[ReversionMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze mean reversion patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Mean reversion analysis results
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
    
    def _calculate_metrics(self, df: pd.DataFrame) -> ReversionMetrics:
        """
        Calculate mean reversion metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            ReversionMetrics object
        """
        close = df['close'].values
        
        # Calculate mean and std
        mean = np.mean(close[-self.lookback_period:])
        std = np.std(close[-self.lookback_period:])
        
        current_price = close[-1]
        
        # Calculate z-score
        if std > 0:
            zscore = (current_price - mean) / std
        else:
            zscore = 0.0
        
        # Calculate mean reversion score
        score = 1 - abs(zscore) / 3  # Normalize to [0, 1]
        score = max(0, min(1, score))
        
        # Calculate half-life
        half_life = self._calculate_half_life(close)
        
        # Calculate deviation
        deviation = current_price - mean
        
        # Calculate confidence
        confidence = 1 - abs(zscore) / 4  # Higher confidence when zscore is moderate
        confidence = max(0, min(1, confidence))
        
        metrics = ReversionMetrics(
            timestamp=datetime.now(),
            zscore=zscore,
            mean=mean,
            std=std,
            current_price=current_price,
            mean_reversion_score=score,
            half_life=half_life,
            deviation=deviation,
            confidence=confidence
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_half_life(self, close: np.ndarray) -> float:
        """
        Calculate half-life of mean reversion.
        
        Args:
            close: Close prices
            
        Returns:
            Half-life in periods
        """
        if len(close) < 3:
            return float('inf')
        
        # Use linear regression on lagged values
        lagged = close[:-1]
        current = close[1:]
        
        slope, intercept = MathUtils.linear_regression(lagged, current)
        
        if slope >= 0:
            return float('inf')
        
        return -np.log(2) / slope
    
    def _get_default_metrics(self) -> ReversionMetrics:
        """
        Get default metrics.
        
        Returns:
            Default ReversionMetrics object
        """
        return ReversionMetrics(
            timestamp=datetime.now(),
            zscore=0.0,
            mean=0.0,
            std=0.0,
            current_price=0.0,
            mean_reversion_score=0.5,
            half_life=float('inf'),
            deviation=0.0,
            confidence=0.5
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: ReversionMetrics) -> List[ReversionSignal]:
        """
        Generate mean reversion signals.
        
        Args:
            df: OHLCV data
            metrics: ReversionMetrics object
            
        Returns:
            List of ReversionSignal objects
        """
        signals = []
        
        if metrics.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check if price is overextended
        if metrics.zscore > self.entry_zscore:
            signal_type = 'sell'
            reason = f"Mean reversion - overbought (z-score: {metrics.zscore:.2f})"
            target = metrics.mean + self.exit_zscore * metrics.std
            stop_loss = metrics.mean + (self.entry_zscore + 0.5) * metrics.std
            confidence = metrics.confidence
            
            signals.append(ReversionSignal(
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
                    'zscore': metrics.zscore,
                    'mean': metrics.mean,
                    'std': metrics.std
                }
            ))
            
        elif metrics.zscore < -self.entry_zscore:
            signal_type = 'buy'
            reason = f"Mean reversion - oversold (z-score: {metrics.zscore:.2f})"
            target = metrics.mean - self.exit_zscore * metrics.std
            stop_loss = metrics.mean - (self.entry_zscore + 0.5) * metrics.std
            confidence = metrics.confidence
            
            signals.append(ReversionSignal(
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
                    'zscore': metrics.zscore,
                    'mean': metrics.mean,
                    'std': metrics.std
                }
            ))
        
        return signals
    
    def _get_status(self, metrics: ReversionMetrics) -> str:
        """
        Get status from mean reversion metrics.
        
        Args:
            metrics: ReversionMetrics object
            
        Returns:
            Status string
        """
        if abs(metrics.zscore) > self.entry_zscore:
            return 'overextended'
        elif abs(metrics.zscore) > self.entry_zscore * 0.5:
            return 'moderate'
        else:
            return 'normal'
    
    def _get_market_character(self, df: pd.DataFrame,
                             metrics: ReversionMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: ReversionMetrics object
            
        Returns:
            Market character description
        """
        if abs(metrics.zscore) > self.entry_zscore:
            return f"Overextended - {metrics.zscore:.2f} z-score"
        elif abs(metrics.zscore) > self.entry_zscore * 0.5:
            return f"Moderate deviation - {metrics.zscore:.2f} z-score"
        else:
            return "Normal range - mean reversion unlikely"
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get mean reversion metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_zscore': np.mean([m.zscore for m in self.metrics_history]),
            'max_zscore': max([m.zscore for m in self.metrics_history]),
            'min_zscore': min([m.zscore for m in self.metrics_history]),
            'average_half_life': np.mean([m.half_life for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_reversion_model(config: Optional[Dict[str, Any]] = None) -> ReversionModel:
    """
    Create a mean reversion model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ReversionModel instance
    """
    return ReversionModel(config)


__all__ = [
    'ReversionMetrics',
    'ReversionSignal',
    'ReversionModel',
    'create_reversion_model'
]
