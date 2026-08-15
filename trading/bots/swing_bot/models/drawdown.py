"""
Swing Bot Drawdown Model
==========================

This module provides drawdown analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class DrawdownMetrics:
    """Drawdown metrics data structure."""
    timestamp: datetime
    max_drawdown: float
    current_drawdown: float
    average_drawdown: float
    recovery_time: float
    drawdown_frequency: float
    ulcer_index: float
    worst_drawdown_period: Tuple[datetime, datetime]
    max_drawdown_duration: float


@dataclass
class DrawdownSignal:
    """Drawdown trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: DrawdownMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class DrawdownModel:
    """
    Drawdown analysis model for risk assessment.
    
    Implements various drawdown metrics for risk management.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the drawdown model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 252)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[DrawdownMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze drawdown metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Drawdown analysis results
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
    
    def _calculate_metrics(self, df: pd.DataFrame) -> DrawdownMetrics:
        """
        Calculate drawdown metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            DrawdownMetrics object
        """
        close = df['close'].values
        dates = df.index
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(close)
        
        # Calculate drawdowns
        drawdowns = (close - running_max) / running_max
        
        # Maximum drawdown
        max_drawdown = np.min(drawdowns)
        max_drawdown_idx = np.argmin(drawdowns)
        
        # Current drawdown
        current_drawdown = drawdowns[-1]
        
        # Average drawdown (excluding periods with no drawdown)
        negative_drawdowns = drawdowns[drawdowns < 0]
        avg_drawdown = np.mean(negative_drawdowns) if len(negative_drawdowns) > 0 else 0
        
        # Recovery time
        recovery_time = self._calculate_recovery_time(close, max_drawdown_idx)
        
        # Drawdown frequency
        drawdown_frequency = len(negative_drawdowns) / len(drawdowns)
        
        # Ulcer Index
        ulcer_index = np.sqrt(np.mean(drawdowns ** 2))
        
        # Worst drawdown period
        max_drawdown_start = np.argmax(running_max[:max_drawdown_idx + 1])
        max_drawdown_end = max_drawdown_idx
        
        # Maximum drawdown duration
        max_drawdown_duration = 0
        in_drawdown = False
        drawdown_start = 0
        
        for i in range(len(drawdowns)):
            if drawdowns[i] < 0 and not in_drawdown:
                in_drawdown = True
                drawdown_start = i
            elif drawdowns[i] >= 0 and in_drawdown:
                in_drawdown = False
                duration = i - drawdown_start
                max_drawdown_duration = max(max_drawdown_duration, duration)
        
        if in_drawdown:
            duration = len(drawdowns) - drawdown_start
            max_drawdown_duration = max(max_drawdown_duration, duration)
        
        metrics = DrawdownMetrics(
            timestamp=datetime.now(),
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            average_drawdown=avg_drawdown,
            recovery_time=recovery_time,
            drawdown_frequency=drawdown_frequency,
            ulcer_index=ulcer_index,
            worst_drawdown_period=(dates[max_drawdown_start], dates[max_drawdown_end]),
            max_drawdown_duration=max_drawdown_duration
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_recovery_time(self, close: np.ndarray, max_idx: int) -> float:
        """
        Calculate recovery time from maximum drawdown.
        
        Args:
            close: Close prices
            max_idx: Index of maximum drawdown
            
        Returns:
            Recovery time in periods
        """
        if max_idx >= len(close) - 1:
            return 0.0
        
        max_price = close[max_idx]
        for i in range(max_idx + 1, len(close)):
            if close[i] >= max_price:
                return i - max_idx
        
        return len(close) - max_idx - 1
    
    def _get_default_metrics(self) -> DrawdownMetrics:
        """
        Get default metrics.
        
        Returns:
            Default DrawdownMetrics object
        """
        return DrawdownMetrics(
            timestamp=datetime.now(),
            max_drawdown=0.0,
            current_drawdown=0.0,
            average_drawdown=0.0,
            recovery_time=0.0,
            drawdown_frequency=0.0,
            ulcer_index=0.0,
            worst_drawdown_period=(datetime.now(), datetime.now()),
            max_drawdown_duration=0.0
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: DrawdownMetrics) -> List[DrawdownSignal]:
        """
        Generate trading signals from drawdown metrics.
        
        Args:
            df: OHLCV data
            metrics: DrawdownMetrics object
            
        Returns:
            List of DrawdownSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check if drawdown is significant
        if abs(metrics.current_drawdown) < self.confidence_threshold:
            return signals
        
        # Generate signal based on drawdown
        if metrics.current_drawdown < -0.10:
            # Significant drawdown - potential buying opportunity
            signal_type = 'buy'
            reason = f"Significant drawdown ({metrics.current_drawdown:.2%}) - potential buying opportunity"
            confidence = min(abs(metrics.current_drawdown) * 2, 1.0)
            target = current_price * 1.05
            stop_loss = current_price * 0.95
            
            signals.append(DrawdownSignal(
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
                    'current_drawdown': metrics.current_drawdown,
                    'max_drawdown': metrics.max_drawdown,
                    'ulcer_index': metrics.ulcer_index,
                    'recovery_time': metrics.recovery_time
                }
            ))
            
        elif metrics.current_drawdown > -0.02:
            # Small drawdown - potential selling opportunity
            signal_type = 'sell'
            reason = f"Small drawdown ({metrics.current_drawdown:.2%}) - potential resistance"
            confidence = min(abs(metrics.current_drawdown) * 2, 1.0)
            target = current_price * 0.95
            stop_loss = current_price * 1.05
            
            signals.append(DrawdownSignal(
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
                    'current_drawdown': metrics.current_drawdown,
                    'max_drawdown': metrics.max_drawdown,
                    'ulcer_index': metrics.ulcer_index,
                    'recovery_time': metrics.recovery_time
                }
            ))
        
        return signals
    
    def _get_status(self, metrics: DrawdownMetrics) -> str:
        """
        Get status from drawdown metrics.
        
        Args:
            metrics: DrawdownMetrics object
            
        Returns:
            Status string
        """
        if metrics.current_drawdown < -0.10:
            return 'high_drawdown'
        elif metrics.current_drawdown < -0.05:
            return 'moderate_drawdown'
        elif metrics.current_drawdown < -0.02:
            return 'low_drawdown'
        else:
            return 'no_drawdown'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: DrawdownMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: DrawdownMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'high_drawdown': f"High drawdown ({metrics.current_drawdown:.2%})",
            'moderate_drawdown': f"Moderate drawdown ({metrics.current_drawdown:.2%})",
            'low_drawdown': f"Low drawdown ({metrics.current_drawdown:.2%})",
            'no_drawdown': f"No drawdown ({metrics.current_drawdown:.2%})"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get drawdown metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_max_drawdown': np.mean([m.max_drawdown for m in self.metrics_history]),
            'average_current_drawdown': np.mean([m.current_drawdown for m in self.metrics_history]),
            'average_ulcer_index': np.mean([m.ulcer_index for m in self.metrics_history]),
            'average_recovery_time': np.mean([m.recovery_time for m in self.metrics_history]),
            'max_drawdown_recorded': min([m.max_drawdown for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_drawdown_model(config: Optional[Dict[str, Any]] = None) -> DrawdownModel:
    """
    Create a drawdown model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        DrawdownModel instance
    """
    return DrawdownModel(config)


__all__ = [
    'DrawdownMetrics',
    'DrawdownSignal',
    'DrawdownModel',
    'create_drawdown_model'
]
